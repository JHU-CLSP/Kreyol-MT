## French Guianese Creole (`gcr`)

### Focus language: African-diaspora Creole language of the Caribbean/Latin America

Resources:
 - bitexts with English (`eng`)
 - bitexts with French (`fra`)
 - monolingual texts

The mono data comes from two sources. The graelo data is 15K lines of raw text from the 20230901 Wikipedia dump. The main extraction was done by graelo - https://huggingface.co/datasets/graelo/wikipedia
I just combined their train and test sets and broke the paragraphs down into lines.
Atipa is a novel published by Alfred Parépou in 1885. The data here is more or less raw OCR output, and could use cleaning at a later time.
Similarly, the bitexts come from "Introduction à l'histoire de Cayenne. Contes, fables et chansons en créole / Alfred de Saint-Quentin", which is also public. Because alignment is time consuming,
only some of the possible bitext is represented, but an effort was made to correct more egregious OCR errors while doing manual alignment.

`wikidumps` data added later.
