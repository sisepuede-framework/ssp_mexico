    #################################################
    # Post processing process
    #################################################

    # load packages
    library(data.table)
    library(reshape2)
    library(mFilter)
    library(ggplot2)
    library(dplyr)

    rm(list=ls())

    #ouputfile

    dir.output  <- "ssp_modeling/ssp_run_output/sisepuede_results_sisepuede_run_2025-10-23T13;32;38.383522/"
    output.file <- "sisepuede_results_sisepuede_run_2025-10-23T13;32;38.383522_WIDE_INPUTS_OUTPUTS.csv"

    region <- "mexico" 
    iso_code3 <- "MEX"

    year_ref <- 2023

    source('ssp_modeling/output_postprocessing/scr/run_script_baseline_run_new.r')

    source('ssp_modeling/output_postprocessing/scr/data_prep_new_mapping.r')

source('ssp_modeling/output_postprocessing/scr/data_prep_drivers.r')

# Levers table
source('ssp_modeling/output_postprocessing/scr/levers_table/#create levers table.r')

# Jobs table
source('ssp_modeling/output_postprocessing/scr/levers_table/#create jobs table.r')