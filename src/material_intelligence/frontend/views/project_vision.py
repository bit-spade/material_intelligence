import hashlib

import streamlit as st

from material_intelligence.api.vision import (
    VisionError,
    detect_room_items,
    find_visual_matches,
    open_room_image,
)


def room_image_materials() -> list[dict]:
    st.caption("Qwen scans the room on the app’s server. A CUDA-enabled runtime is required.")
    image_file = st.file_uploader("Upload a room image", type=["jpg", "jpeg", "png", "webp"])
    if image_file is None:
        st.session_state.pop("room_scan", None)
        return []

    raw = image_file.getvalue()
    image_id = hashlib.sha256(raw).hexdigest()
    scan = st.session_state.get("room_scan")
    if scan is None or scan["image_id"] != image_id:
        scan = {"image_id": image_id, "detections": None, "matches": {}, "chosen": {}}
        st.session_state.room_scan = scan
    try:
        image = open_room_image(raw)
    except VisionError as exc:
        st.error(str(exc))
        return []
    with st.expander("Room preview", expanded=scan["detections"] is None):
        st.image(image, width="stretch")
    if st.button("Detect interior items", type="primary"):
        try:
            with st.spinner("Detecting interior items…"):
                scan["detections"] = detect_room_items(image)
        except VisionError as exc:
            st.error(str(exc))
            return []
        scan["matches"].clear()
        scan["chosen"].clear()
    detections = scan["detections"]
    if detections is None:
        return []
    if not detections:
        st.info("No objects were detected. Try another image or add materials manually.")
        return []

    labels = {i: f"{detection.label} ({i + 1})" for i, detection in enumerate(detections)}
    widget_prefix = f"room_scan_{image_id[:12]}"
    selected = st.multiselect(
        "Items to review", labels, default=list(labels), format_func=labels.get, key=f"{widget_prefix}_items",
    )
    active = st.selectbox(
        "Preview or match an item", selected, format_func=labels.get, key=f"{widget_prefix}_preview",
    )
    if active is not None:
        detection = detections[active]
        crop = image.crop(detection.box)
        st.image(crop, caption=detection.label, width=150)
        st.caption("Visual search sends only this crop to SerpApi.")
        if st.button("Find visual matches", key=f"{widget_prefix}_find_{active}"):
            try:
                with st.spinner("Finding similar products…"):
                    scan["matches"][active] = find_visual_matches(crop, detection.label)
            except VisionError as exc:
                st.error(str(exc))
        if active in scan["matches"]:
            matches = scan["matches"][active]
            if matches:
                options = {match.url: match for match in matches}
                urls = [None, *options]
                previous = scan["chosen"].get(active)
                default = previous.url if previous and previous.url in options else None
                url = st.selectbox(
                    "Product match", urls, index=urls.index(default),
                    format_func=lambda url: f"{options[url].title} · {options[url].source}" if url else "Use detected name",
                    key=f"{widget_prefix}_match_{active}",
                )
                scan["chosen"][active] = options.get(url)
                if url:
                    st.link_button("Open product source", url)
            else:
                st.info("No visual matches were returned for this item.")

    if not st.button("Review selected items", disabled=not selected, type="primary"):
        return []
    rows = []
    for index in selected:
        match = scan["chosen"].get(index)
        rows.append({
            "name": match.title if match else detections[index].label,
            "url": match.url if match else "",
            "quantity": 1,
        })
    return rows
