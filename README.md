# 🌿 Material Intelligence

*An AI-assisted multi-criteria environmental assessment tool for greener interiors.*

Material Intelligence helps interior designers evaluate, compare, and select more sustainable finishing materials using a questionnaire-based **ECO-SCORE** methodology.

## About the Project

Interior design must balance comfort, aesthetics, durability, and environmental responsibility. Materials used in the “soft layer” of interiors can contribute to microplastic pollution, carbon emissions, chemical exposure, resource depletion, and short product lifecycles.

**Material Intelligence** connects life-cycle assessment principles with practical material selection. The project was developed in cooperation with the **Faculty of Architecture at Poznań University of Technology, Poland**.

The application uses product documentation, technical data, and user-provided notes to assess interior materials across several environmental and performance criteria.

> **Important:** ECO-SCORE is a comparative decision-support tool. It does not replace a complete third-party-verified life-cycle assessment, Environmental Product Declaration, regulatory certification, or professional environmental audit.

## Features

- Questionnaire-based ECO-SCORE assessment
- AI-assisted interpretation of product documentation
- Support for textile, acoustic, and lighting products
- Uploading technical documents and supporting materials
- Sustainability classification based on the calculated percentage score
- Reference benchmarks for selected example products
- Streamlit web interface
- Structured scoring logic implemented in Python

## Supported Material Categories

### Textiles

Examples include upholstery, curtains, carpets, and other textile-based interior products.

The assessment considers factors such as:

- Raw material sourcing
- Recycled and renewable content
- Chemical safety
- PFAS/PFC avoidance
- Durability and Martindale abrasion resistance
- Product documentation and transparency
- Recyclability and end-of-life considerations

### Acoustics

Examples include acoustic panels, acoustic plasters, and other sound-absorbing interior products.

The assessment considers factors such as:

- Dust and particle emissions
- Indoor air-quality impact
- Material composition
- Modularity and repairability
- Installation and maintenance
- Circular-economy potential
- Availability of environmental documentation

### Lighting

Examples include luminaires, fixtures, and LED lighting products.

The assessment considers factors such as:

- Corrosion resistance
- Mechanical impact resistance
- WEEE compliance
- Component separation
- Repairability and replaceability
- Energy-related information
- Recyclability and end-of-life handling

## ECO-SCORE Classification

The current application classifies products into three sustainability levels:

| Level | Score |
|---|---:|
| **High** | 75% or above |
| **Medium** | 40%–74% |
| **Low** | Below 40% |

The score is calculated from the points awarded for the relevant product questionnaire and is presented together with the maximum possible score and percentage result.

## Reference Results

The application includes benchmark references based on selected example products:

| Category | Product | Score | Classification |
|---|---|---:|---|
| Textiles | SIDDE LIV sofa | 84% | High |
| Textiles | IKEA MAJGULL curtain | 65% | Medium |
| Acoustics | Ecophon Fade One Smooth | 89% | High |
| Acoustics | Addictive Sound panels | 47% | Medium |
| Lighting | Disano 1774 Amalfi luminaire | 70% | Medium |
| Lighting | 300 W LED street light | 9.23% | Low |

These examples illustrate how product transparency, environmental documentation, durability, chemical information, and circularity can influence the final result.

## Methodology

The ECO-SCORE methodology is informed by principles and guidance related to:

- ISO 14040 and ISO 14044 life-cycle assessment principles
- ISO 14021 environmental claims
- EU Ecolabel guidance
- Environmental Product Declarations
- Product documentation and chemical-safety information
- Circular design and end-of-life considerations

The final score depends on the quality and completeness of the available product information. Missing documentation may reduce the score because environmental performance cannot be verified.

## Technology Stack

- **User interface:** Streamlit
- **Programming language:** Python 3.11+
- **Data validation:** Pydantic
- **AI integration:** Google Gemini through LangChain
- **Document processing:** PyPDF and `docx2txt`
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
│       │   ├── chat.py
│       │   ├── utils.py
│       │   └── schemas/
│       ├── engine/
│       │   └── calculator.py
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
- A Google Gemini API key
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
```

Do not commit `.env` files or API keys to version control.

## Running the Application

Using `uv`:

```bash
uv run streamlit run src/material_intelligence/frontend/streamlit.py
```

Using an activated Python environment:

```bash
streamlit run src/material_intelligence/frontend/streamlit.py
```

The application opens in a browser and provides an interface for selecting a product category, uploading documentation, entering additional notes, and starting an assessment.

## Supported Upload Formats

The application supports the following file types:

- PDF
- PNG
- JPG and JPEG
- TXT
- CSV

Uploaded files should contain relevant product information, such as:

- Technical datasheets
- Environmental Product Declarations
- Material composition information
- Chemical-safety documentation
- Durability and performance data
- Recycling or end-of-life information
- Product certificates

## Roadmap

- [x] Questionnaire-based Streamlit calculator
- [x] AI-assisted assessment using uploaded documentation
- [x] Textile, acoustic, and lighting product categories
- [ ] Project-level material aggregation
- [ ] Automatic extraction and normalization from technical documents
- [ ] Search by product and manufacturer name
- [ ] Product recommendations
- [ ] Image-based material analysis

## Limitations

ECO-SCORE results depend on the quality, availability, and accuracy of the information supplied by the user or manufacturer.

The application:

- Does not perform a complete certified LCA
- Does not independently verify manufacturer claims
- Does not replace regulatory or professional certification
- May produce less reliable results when product documentation is incomplete
- Should be used to support, not replace, professional design and procurement decisions

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