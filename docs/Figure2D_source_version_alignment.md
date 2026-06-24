# Figure 2D Source-Version Alignment

The final Figure 2D distribution is based on the later 491-row closure run:

`EMSAv1-Map of Evidence/491_evidence_map_final_landscape_closure_20260607_214625`

The release-ready aggregate source is:

`data/figure_source_data/figure2_Figure2D_omics_distribution_input_closure.csv`

The legacy filename `figure2_figure2B_omics_distribution_input_repaired.csv` is retained for compatibility, but its contents have been synchronized to the closure distribution.

The older row-level file `figure2_491_evidence_map_master_table_repaired.csv` predates the closure reclassification of 68 initially unclear primary-omics records. It must not be used to regenerate final Figure 2D counts.

Final count checks:

- 491 unique evidence records;
- category counts sum to 491;
- Multi-omics: 206;
- Microbiome: 171;
- Transcriptomics: 37;
- Metabolomics: 28;
- Virome: 17;
- Proteomics: 8;
- Metagenomics: 8;
- Mycobiome: 6;
- Epigenomics: 5;
- Genomics: 3;
- Unclear/not classified: 1;
- Other, specified: 1.

The broad `Microbiome` category should not be labelled `Amplicon microbiome`, because four records do not have a bacterial amplicon subtype. The eight primary `Metagenomics` records are all coded as shotgun metagenomics.
