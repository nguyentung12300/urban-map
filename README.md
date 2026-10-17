# Urban Map — Automated GIS, Space Syntax & AI Urban Design Intelligence

[![MIT License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
![Python GIS](https://img.shields.io/badge/Python-GIS-blue.svg)
![Space Syntax](https://img.shields.io/badge/Space_Syntax-depthmapXcli-orange.svg)
![Docker](https://img.shields.io/badge/Docker-ready-2496ED.svg)
[![Live Demo](https://img.shields.io/badge/Live_Demo-maps.nqt.best-2ea44f.svg)](https://maps.nqt.best)

> **Public repository scope:** this repository contains a small, standalone GeoJSON validation library and a safe depthmapXcli process wrapper. It does not publish the production backend, authentication code, database configuration, deployment secrets, or private survey data.

## Overview

Urban Map is a free-to-access, open-source urban analysis platform developed at Hanoi Architectural University (HAU). It helps urban design students, architects, and climate researchers automate site-analysis workflows from a study-area location.

The platform combines standardized GIS outputs, Space Syntax analysis, walkability diagnostics, field survey tools, and evidence-linked design insights. This public repository publishes selected reusable modules and deployment examples; the full production application remains available as a live service at [maps.nqt.best](https://maps.nqt.best).

## Core Features

### 7 Standardized GIS Map Layers

Urban Map automates extraction from OpenStreetMap and planning sources into seven standardized layers: **VT01–03**, **ST01**, **LH01**, **GT01**, and **KH01**. Together they describe administrative context, planning, blue-green space, amenities, street networks, and sun-and-wind conditions.

For the Pasteur Flower Garden sample case, the displayed examples include **8.7% green coverage** in ST01 and **12.6 km/km² road density** in GT01. These values describe that sample study area and are not universal benchmarks.

### Headless Space Syntax & Walkability Diagnostics

The analysis pipeline uses **depthmapXcli** for headless Space Syntax workflows across a documented study network of **33,216 street segments**. It evaluates the walking network at **R400, R800, and R1200**; AC01–03 diagnostics cover network-based reachability and walkable isochrones.

A representative 800 m sample reports **26 bus stops within the Euclidean radius and 16 reachable on the walking network**, a **2.67** detour ratio, and a **15.71%** dead-end-road share. These are study-specific outputs; rerun the analysis with the study boundary and source snapshot you need.

### Interactive Field Survey & Digitization

The Urban Map application supports field surveys on an interactive map, browser GPS, point/line/polygon drawing, six urban-data layers, and GeoJSON export. The standalone public package includes a canonical validator for Point, LineString, and Polygon FeatureCollections.

### Evidence-Based SWOT Matrix

The platform generates evidence-linked SWOT strategies. GIS claims can point back to metrics such as **LH01**, **GT01**, and **ST01**, while planning-document claims carry source references such as **EXT_FACT**. This makes each finding traceable to the data behind it.

### Reusable Python Modules in This Repository

The public package exposes two dependency-free helpers:

- **GeoJSON normalization:** validates coordinate ranges, feature and vertex limits, JSON properties, and polygon ring closure.
- **depthmapXcli wrapper:** runs a local executable with argument-list semantics, a timeout, shell execution disabled, and a reduced child-process environment.

~~~python
from urban_map_public import normalize_feature_collection

survey = {
    "type": "FeatureCollection",
    "features": [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [0, 0]},
            "properties": {"layer_id": "field-notes", "condition": "good"},
        }
    ],
}

canonical = normalize_feature_collection(survey)
~~~

~~~python
from urban_map_public import run_depthmapx

version = run_depthmapx(["-v"])
print(version.stdout.strip())
~~~

The wrapper invokes the binary supplied by the deployment. **depthmapXcli is an external dependency and retains its own upstream licensing and distribution terms.**

## Screenshots

The paths below are reserved for sanitized application screenshots. Add the corresponding image files before publishing the screenshot gallery; do not include real survey coordinates, personal information, or private project identifiers.

![Seven standardized GIS layers for one urban study area](docs/images/01-seven-layers.png)

*Seven standardized map layers generated for a single study area.*

![Interactive field survey and map digitization workspace](docs/images/02-field-survey.png)

*Field teams record point, line, and polygon observations directly on the map.*

![Headless Space Syntax analysis with depthmapXcli](docs/images/03-space-syntax.png)

*Space Syntax outputs summarize segment analysis at multiple metric radii.*

![Walking-network accessibility diagnostics](docs/images/04-accessibility-diagnostics.png)

*Network reachability and isochrones reveal practical walking access.*

![Evidence-linked SWOT analysis](docs/images/05-evidence-swot.png)

*Each SWOT statement links to a GIS metric or a cited planning fact.*

## System Architecture

The production workflow runs in Docker:

~~~text
Browser
  └── Frontend
        └── Backend API and job orchestration
              └── Python GIS Map Worker
                    ├── OpenStreetMap and planning-data processing
                    ├── GIS metrics, GeoJSON surveys, and accessibility outputs
                    └── depthmapXcli for headless Space Syntax analysis
~~~

The Map Worker image must contain the depthmapXcli executable at the configured path. The optional Compose diagnostics container is a one-shot CLI runner, not an API service. This repository intentionally omits the production Frontend, Backend, queue, and worker implementation.

## Installation & Run

### Install the standalone Python package

Python 3.11 or later is required. The package has no runtime Python dependencies.

~~~bash
python -m venv .venv
~~~

Activate the virtual environment for your shell, then install from the repository root:

~~~bash
python -m pip install -e .
python -c "from urban_map_public import normalize_feature_collection; print('Urban Map public modules are ready')"
~~~

To use the CLI wrapper, install a compatible depthmapXcli binary separately and set its path:

~~~bash
export DEPTHMAPX_CLI_PATH=/usr/local/bin/depthmapXcli
python -c "from urban_map_public import run_depthmapx; print(run_depthmapx(['-v']).stdout)"
~~~

On PowerShell, set the variable with:

~~~powershell
$env:DEPTHMAPX_CLI_PATH = "C:\tools\depthmapXcli.exe"
~~~

### Compose integration example

The Compose file references local images; the production worker and depthmapXcli images are deliberately not included in this public repository.

~~~bash
cp .env.example .env
docker compose -f docker-compose.example.yml config
docker compose -f docker-compose.example.yml up -d map-worker
docker compose -f docker-compose.example.yml run --rm depthmapx-cli -v
~~~

Build or obtain the two local images first. The Map Worker image must include the Python service and depthmapXcli at the path in DEPTHMAPX_CLI_PATH. The optional depthmapx-cli service only checks or runs the binary on demand. Do not expose a worker endpoint publicly without authentication and a reverse proxy.

## Data Attribution

Urban Map outputs that use OpenStreetMap data should credit **© OpenStreetMap contributors** and link to the [OpenStreetMap copyright and license page](https://www.openstreetmap.org/copyright). OpenStreetMap data is licensed under the Open Database License (ODbL); this data license is separate from the MIT license for the code in this repository.

Planning data and depthmapXcli may have their own source-specific terms. Review those terms before redistributing source data, rendered outputs, or binaries.

## Security & Privacy

- Never commit a real .env file, API key, database credential, access token, private survey, or unredacted project artifact.
- The .gitignore file blocks common secret names, environment files, and raw geospatial exports. Review staged files before publishing; ignore rules are a safety net, not a substitute for inspecting a public commit.
- The .env.example file contains local image names and a binary path only; it contains no credentials.
- The GeoJSON validator preserves feature properties and coordinates. It does not anonymize personal or location data.

## License

The code in this repository is available under the MIT License. See [LICENSE](LICENSE).
