
  # Re Search

**Re Search** is a Logic2 extension that adds searches for text matching a given
regular expression in textual output from low level analyzers and outputs the
matched text.

![](ReSearch.png)

This is a useful tool for finding text of interest and quickly navigating
between matches using Logic's skip facilities.

## Instructions

Install **ReSearch** by clicking "Install" on the **Re Search** entry in the
Extensions panel.

Use the Analyzers side panel to add a Re Search analyzer to a suitable low level
analyser.

In the ReSearch Settings dialog select the required input analyzer then set the
regular expression match string. Python regular expression syntax is used for
the match string. Note that the provided match is not checked for syntax errors
- a badly formed string will generate a somewhat cryptic error dialog in Logic!

