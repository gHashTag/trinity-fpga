# Canon plates

<!-- orphan-artefacts: drawn-not-computed -->

The images in this directory are drawn illustration plates. The paper places
them with `\includegraphics{canon/...}` under captions that begin
"Canon plate.", and each one restates in pictures an argument the surrounding
text makes in words.

They are **made, not computed**. No script draws them and none ever will, so the
orphan-artefacts gate (`tools/check_orphan_artefacts.py`) would count every one
of them as an artefact no code produces. The marker above declares that this
directory holds figures of that kind. The gate honours it for figures only
(`.png`, `.pdf`, `.svg`) and prints, on every run, how many artefacts rely on
the declaration, so the exemption stays visible rather than becoming a silence.

What the declaration does **not** cover:

- **Data.** A `.json` placed here is still checked. A measurement that no code
  produces is never "drawn".
- **Numbers.** A plate is not a source. Any figure a plate depicts must be
  stated, and sourced, in the text it illustrates. When the text withdraws or
  qualifies a number, the plate that shows it is redrawn or removed with it.
- **Use.** One plate, number 09 (retractions), is not placed by the paper at
  all. It is kept here pending the author's decision, not because anything
  cites it.
