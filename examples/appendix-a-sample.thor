; Appendix A-derived tree/list sample for THOR syntax highlighting.
tree |= label subtrees

sample-tree == {tree ROOT
  [{tree LEFT []}
   {tree RIGHT []}]}

labels == [X O E]

first-label == (car labels)

sample-tree
