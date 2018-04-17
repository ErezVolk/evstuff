This InDesign script (work in progress) aims to make things a little bit easier
on people importing files into InDesign, especially if the InDesign project is
a book with little or no non-text material.

To install the script, copy it to the user script folder. When you run it, it
will display an option dialog with a number of checkboxes.  More detailed
documentation will come one day, but here's a basic outline of the
functionality provided.

**BACKUP YOUR DATA. THINGS MAY BREAK.**

![ReImport Options](ReImport.png?raw=true).

- "Pre-Import" group: Cleaning up before the import
  - "Reset all master pages": Before importing, set all master pages to the Default Master.
  - "Remove all text": Does what it says. Note that if your document has multiple (main) stories and such, this probably won't work.
- "Import" group
  - "Regenerate tagged text if applicable": Integration with another script of mine, not really meaningful otherwise.
  - " Show import options": Whether to display InDesign's "Place Options" dialog.
- "Post-Import" group:
  - "Clear all imported style overrides": Get rid of any manual (non-style) formatting.
  - "Eliminate multiple spaces": Get rid of those annoying sequences of whitespace.
  - "Fix spacing around dashes": Chage the spacing before a dash to a (non-breaking) thin space, and after a dash an optional line break and another thin space.
  - "Remove leading whitespace in footnotes": Word tends to use those. InDesign doesn't.
- "Grooming" group: things you'll want to redo when you edit your InDesign document and text moves around.
  - "Fix to full justification": If you have justified paragraphs and the final line is almost at the edge, change to fully justified. Currently right-to-left paragraphs only. Probably not a good choice for Arabic.
  - "Fix master pages": Tries to guess which pages need the "Headless Master".
