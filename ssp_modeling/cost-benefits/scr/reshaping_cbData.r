library(data.table)

#lets just bring in the 
#read all folders 
dir.data <- "ssp_modeling/cost-benefits/output/"
target_cb_file <- "cba_results.csv"
cb_data <-read.csv(paste0(dir.data,target_cb_file))

cb_chars <- data.frame(do.call(rbind, strsplit(as.character(cb_data$variable), ":")))
colnames(cb_chars) <- c("name","sector","cb_type","item_1","item_2")
cb_data <- cbind(cb_data,cb_chars)
cb_data$value <- cb_data$value/1e9

#remove shifted 
dim(cb_data)
cb_data <- subset(cb_data,grepl("shifted",cb_data$item_2)==FALSE)
dim(cb_data)
ids <- unique(cb_data$variable)
ids <- subset(ids,grepl("shifted2",ids)==FALSE)

#clean  
cb_data <- subset(cb_data,grepl("shifted2",cb_data$variable)==FALSE)
dim(cb_data)

#add Year 
cb_data$Year <- cb_data$time_period+2015

head(cb_data)
table(cb_data$Year)

table(cb_data$strategy)

#change strategy names
cb_data$strategy <- gsub("EN:ALL", "NDC + (Energy)", cb_data$strategy)
cb_data$strategy <- gsub("PFLO:NDC", "NDC", cb_data$strategy)
cb_data$strategy <- gsub("PFLO:ALL", "Low Emissions Pathway", cb_data$strategy)

table(cb_data$strategy_code)

#create strategy id 
cb_data$strategy_id <- ifelse(cb_data$strategy_code=="EN:ALL", 6004,
							  ifelse(cb_data$strategy_code=="PFLO:NDC", 6005,
							  ifelse(cb_data$strategy_code=="PFLO:ALL", 6006, cb_data$strategy_code)))
							  
cb_data$ids <- paste(cb_data$variable,cb_data$strategy_id,sep=":")


table(cb_data$strategy)
table(cb_data$strategy_id)
table(cb_data$strategy_code)

dir.out <- "ssp_modeling/tableau/data/"
write.csv(cb_data,paste0(dir.out,"cb_data.csv"),row.names=FALSE)
