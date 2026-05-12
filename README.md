# houston-lead-gen-parser
Automated Python tool for parsing Harris County property records and filtering high-priority solar leads using entity recognition (LLC/Builders)


I did this project in Google Colab, so the first two parts of the code worked with Chrome.



The Data Parser - This is the core of the system. The script parses raw text from a PDF and, using regular expressions, extracts key data, converting it into a structured DataFrame (table).



The Lead Qualifier - The final filtering stage. The script filters out irrelevant deal types, eliminates duplicates, and excludes popular offers specifically for targeted real estate buyers, creating a ready-made list for the sales department.
