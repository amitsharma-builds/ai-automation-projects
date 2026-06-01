# Lead Qualifier Agent

## What it does
Takes a CSV of company names, researches each one using 
Claude AI, scores them 1-10 as potential leads for AI 
automation services, and outputs a qualified leads CSV.

## How to run
1. Add your Anthropic API key to .env file
2. pip install -r requirements.txt
3. python lead_qualifier.py
4. Check qualified_leads.csv for results

## Tools Used
- Python + Pandas
- Anthropic Claude API
- python-dotenv (secure key management)
- Cursor IDE (vibe coding)

## Business Value
Replaces hours of manual lead research with a 
seconds-long automated process. Scalable to 
thousands of leads.
