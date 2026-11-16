# Material Intelligence

*An AI-assisted multi-criteria environmental assessment tool for greener interiors.*

Material Intelligence helps interior designers evaluate, compare, and select more sustainable finishing materials using the **Interior EcoScore** methodology.

## Live Demo

The demo runs the version deployed from the main branch. [Open Material Intelligence](https://eco-score-materials.streamlit.app)

## About the Project

Interior design must balance comfort, aesthetics, durability, and environmental responsibility. Materials used in the “soft layer” of interiors can contribute to microplastic pollution, carbon emissions, chemical exposure, resource depletion, and short product lifecycles.

**Material Intelligence** connects life-cycle assessment principles with practical material selection. The project was developed in cooperation with the **Faculty of Architecture at Poznań University of Technology, Poland**.

The application uses product documentation, technical data, and user-provided notes to assess interior materials across several environmental and performance criteria.

EcoScore supports comparative decisions during design. For formal environmental assessment, refer to third-party-verified life-cycle assessments, Environmental Product Declarations, and applicable standards.

## Project workflow

1. **Upload materials.** Import CSV, TXT, XLSX, or EcoScore project JSON. You can also enter materials manually, scan a room image, or open the bundled sample.
2. **Verify the list.** Confirm each material's group, quantity, and unit. Include product page links, PDF/DOCX/TXT documents, or notes as evidence.
3. **Assess and improve.** Review the mass-weighted project score, five category scores, evidence, and hotspots. Shortlist products to find alternatives. Selecting a replacement recalculates the project with its mass and scores.
4. **Export.** Download the final material list and the EcoScore report as CSV files.

The CSV template uses `name,category,link,amount,units` headers. XLSX import reads the first worksheet. EcoScore JSON can include pre-extracted attributes or manually supplied category scores and total mass. The sample project includes pre-extracted evidence and pendant-lamp alternatives from the supplied coverage data.

## Methodology

The extraction prompt collects 18 attributes from product sources. The Python calculator uses those attributes to assess 13 questions across 18 product groups, including furniture, flooring, textiles, lighting, and sanitaryware. Missing evidence uses the defaults for the relevant product group.

The Common Materials Framework categories are Climate Health, Human Health, Ecosystem Health, Social Health & Equity, and Circular Economy. The calculator averages the applicable categories. A category score at or below 33 after rounding caps the result at 66. The score bands are red (0–33), orange (34–66), and green (67–100).

Material mass equals quantity multiplied by mass per functional unit. Project category scores are weighted by material mass. Hotspot ranking combines each material's mass share and the distance of its score from 100. The annual climate footprint uses the calculator's assumptions for production, transport, service life, and applicable use phases.

**The reference data include placeholder factors. The current numerical results are for testing.** The calculator emits reference and evidence notes in both the app and the exported report.

## Technology Stack

- **User interface:** Streamlit
- **Programming language:** Python 3.11+
- **Data validation:** Pydantic
- **AI integration:** Google Gemini through LangChain for evidence extraction and alternative sourcing
- **Document processing:** PyPDF and `docx2txt`
- **Room image detection:** Qwen2.5-VL through Transformers with optional SerpApi visual search
- **Configuration:** Environment variables loaded with `python-dotenv`
- **Dependency management:** `pyproject.toml` and `uv.lock`

## Project Structure

```text
material_intelligence/
├── data/
│   ├── Acoustic_product.json
│   ├── Lighting_product.json
│   └── Textile_product.json
├── docs/
│   └── RESULT.md
├── src/
│   └── material_intelligence/
│       ├── api/
│       │   ├── ecoscore.py
│       │   ├── vision.py
│       │   └── schemas/
│       ├── engine/
│       │   ├── ecoscore_calculator.py
│       │   └── ecoscore_reference.json
│       ├── models/
│       │   └── eco_score_points.py
│       ├── frontend/
│       │   └── streamlit.py
│       └── config.py
├── pyproject.toml
├── uv.lock
└── README.md
```

## Requirements

- Python 3.11 or newer
- `uv` or `pip`

## Installation

### Option 1: Using `uv`

Install dependencies and the project:

```bash
uv sync
```

### Option 2: Using `pip`

Install the project in editable mode:

```bash
pip install -e .
```

## Configuration

Create a `.env` file in the project root:

```env
GEMINI_API_KEY=your_gemini_api_key_here
SERPAPI_API_KEY=your_serpapi_api_key_here
```

Gemini reads product evidence and searches for live alternatives. With the key unset, the app can score pre-extracted evidence and use group defaults. The SerpApi key enables optional visual search. Keep both keys in environment variables or local secrets.

## Running the Application

With `uv`, run the Streamlit entry point.

```bash
uv run streamlit run src/material_intelligence/frontend/streamlit.py
```

With an activated Python environment, run Streamlit directly.

```bash
streamlit run src/material_intelligence/frontend/streamlit.py
```

### Room image scanning

Install the optional vision dependencies on the app host with a CUDA-compatible GPU and driver.

```bash
uv sync --extra vision
uv run --extra vision streamlit run src/material_intelligence/frontend/streamlit.py
```

The first scan downloads the Qwen2.5-VL-7B-Instruct weights. The app loads the model on demand with 4-bit quantization. Select **Scan a room image**, upload a JPG, PNG, or WebP file, and review the detected items. You can add the detected labels directly to the verification list. Clicking **Find visual matches** sends the selected item crop and the item's label to SerpApi and offers product links to review. [Qwen model card](https://huggingface.co/Qwen/Qwen2.5-VL-7B-Instruct) · [SerpApi image upload](https://serpapi.com/google-lens-upload-an-image)

### Tests

```bash
uv run python -m unittest discover -s tests
```

## Streamlit Deployment

The application is deployed with [Streamlit Community Cloud](https://streamlit.io/cloud).

Deployment settings:

```text
Repository: bit-spade/material_intelligence
Branch: main
Main file: src/material_intelligence/frontend/streamlit.py
```

Add the Gemini API key in the app's **Settings → Secrets** to enable live extraction and sourcing.

```toml
GEMINI_API_KEY = "your_gemini_api_key_here"
```

The API key must not be committed to the repository. For local development, store it in a `.env` file, which is excluded by `.gitignore`.

## Authors and Acknowledgments

### Project Researchers

- Tsimur Bardziyan
- Andrii Pikuza
- Elizaveta Mishchanka
- Fiodor Kurmanov
- Viacheslav Tkachenka

### Academic Supervisor

dr hab. inż. prof. PP Dariusz Brzeziński

### Institution

Faculty of Informatics and Telecommunications  
Poznań University of Technology  
Politechnika Poznańska

## License

See `LICENSE` for licensing information.
