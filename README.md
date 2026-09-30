# Socratic_AI_judge_pipeline
Repository has code to rate each socratic conversation produced from our data generation pipeline. Based on rating we shall choose high quality conversations for fine-tuning.

## First time setup before running the code

Inside the parent folder:
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install openai python-dotenv
```

## To run the pipeline

```bash
python3 code/pipeline.py --source-model-dir Google_gemini-3.6-flash --max-conversations 5
```