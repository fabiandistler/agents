if (!requireNamespace("DiagrammeR", quietly = TRUE)) {
    stop("Install DiagrammeR to render C4-like diagrams.")
}
DiagrammeR::grViz(
    "
  digraph {
    graph [rankdir = TB, splines = ortho]
    node [shape = box, style = filled]
    Dev   [label = 'R Developer', fillcolor = lightblue]
    Pkg   [label = 'R Package (R/, tests/, man/, data/)', fillcolor = lightgreen]
    CRAN  [label = 'CRAN/GitHub', fillcolor = lightgray]
    User  [label = 'End User', fillcolor = lemonchiffon]
    Dev -> Pkg [label = 'builds/tests/docs']
    Pkg -> CRAN [label = 'releases']
    User -> Pkg [label = 'library(), ::']
  }
"
)
