# SSP_Mexico
This repository stores the notebook to run the SSP model on Mexico's mitigation scenarios.

## Get Started

Create a conda environment with Python 3.11 (you can use any name):

```bash
conda create -n sisepuede python=3.11
```

Activate the environment:

```bash
conda activate sisepuede
```

Install the working version of the sisepuede package:

```bash
pip install git+https://github.com/jcsyme/sisepuede.git@working_version
```

Install the cost benefits package:

```bash
pip install git+https://github.com/milocortes/costs_benefits_ssp.git@main
```

Install additional libraries:

```bash
pip install -r requirements.txt
```

## What's in the notebook
- Automatic completion of missing inputs in Mexico's data using the Costa Rica example.
- Handling of the Scenarios Excel for WEM, WAM, and NZ.
- Creation of new transformations.
- Creation and update of new strategies.

## What's missing
- Some transformation YAMLs need to be updated manually. Please check the logs of the transformation creation cell to know which ones.
