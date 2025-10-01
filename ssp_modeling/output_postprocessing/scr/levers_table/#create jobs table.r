rm(list=ls())

#create jobs table 
jobs_table <- read.csv("ssp_modeling/output_postprocessing/data/levers/Sisepuede - Employment Results - WB (SECTOR).csv")

dim(data.frame(unlist(strsplit(jobs_table$Strategy,": "))))

head(jobs_table)

#read the transformation table
ssp_table <- read.csv(paste0(dir.output,"tableau_levers_table.csv" ))
ssp_table$transformation_code <- gsub("TFR:","",ssp_table$transformer_code)

head(ssp_table)

#read descriptions 
desp <- read.csv("ssp_modeling/output_postprocessing/data/levers/ssp_descriptions.csv")
#read stakeholder codes 
scodes <- read.csv("ssp_modeling/output_postprocessing/data/levers/stakeholder_codes.csv")
scodes$transformation_code <- gsub("TX:","",scodes$transformation_code)


#merge 
dim(ssp_table)
dim(desp)
ssp_table <- merge(ssp_table,desp,by="transformation_code")
dim(ssp_table)
ssp_table <- merge(ssp_table,scodes[,c("transformation_code","transformation_name_stakeholder","Sector..output.","Subsector..output.","Example.government.policies")],by="transformation_code")
dim(ssp_table)

ssp_table <- merge(ssp_table, jobs_table)


write.csv(ssp_table,"/Users/edmun/Library/CloudStorage/OneDrive-Personal/Edmundo-ITESM/3.Proyectos/51. WB Decarbonization Project/Uganda_NDC_3/Tableau/2025_09_27/tableau_levers_table_complete.csv")
