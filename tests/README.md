# Test CVs for the reader

Nine made-up CVs, one per layout that real CVs use. The person in them is invented:
no real CV is ever kept in this repository.

| File | What it tests |
|---|---|
| `plain.pdf` | one column, dates on the right of the job title |
| `sidebar.pdf` | a coloured sidebar of skills beside the main text (the Canva shape) |
| `table.pdf` | a Word table: dates in a left column, the job in a right column |
| `custom.pdf` | the person's own section names ("PLACES I HAVE WORKED", "SCHOOLING") |
| `narrow.pdf` | two equal columns of running text |
| `bullets.pdf` | bullet characters stuck to the first word |
| `twopage.pdf` | two pages, with a repeated header and "Page 1 of 2" at the foot |
| `word.docx` | a Word file with custom section names |
| `scanned.pdf` | a picture of a CV, with no text in it at all |

`node make.js` rebuilds the PDFs, `node mkdocx.js` the Word file.

What a good reader gives, as of phase 1 (Nov 14, 2026): every file except `scanned.pdf`
reads with the right sections and the right career stage, and `scanned.pdf` is refused
with a message that says the file is a picture.
