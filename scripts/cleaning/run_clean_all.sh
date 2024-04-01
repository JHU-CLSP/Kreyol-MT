# CHANGE THESE PATHS
DATA_OUT_PATH="" # Path to the output directory of gen_datasets.py
CLEANING_INFO_OUT_PATH="" # Path to the output directory of clean_all.py; you can ignore this if you don't want to see the cleaning info
CLEAN_TRAIN=True # Set to True if you want to clean the training data; set to False if you want to clean the dev and test data


# Start timer
start=$(date +%s.%N)

# First extract fresh data from the raw data files
cd ..
python gen_datasets.py ../ $DATA_OUT_PATH

# Clean the data
cd cleaning
python clean_all.py $DATA_OUT_PATH $CLEANING_INFO_OUT_PATH --clean_train $CLEAN_TRAIN

# End timer
end=$(date +%s.%N)

# Print time elapsed in minutes and seconds
echo "Time elapsed: " $(echo "($end - $start) / 60" | bc) "minutes" $(echo "($end - $start) % 60" | bc) "seconds"