#!/usr/bin/env python

import warnings
from xgboost import XGBClassifier 
from sklearn.metrics import accuracy_score, classification_report, f1_score 
from sklearn.model_selection import train_test_split
from sklearn.svm import LinearSVC
from sklearn.feature_selection import SelectFromModel
from sklearn.ensemble import ExtraTreesClassifier
from itertools import combinations
import csv
import sys
import shap
import numpy as np
from config import genomeFeaturesFilePath, proteomeFeaturesFilePath, numIterations
import argparse
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

SHAP_PLOT_PATH="../results/shap_values.pdf"
SHAP_PLOT_PATH_2="../results/shap_values_global.pdf"

plt.rcParams['font.sans-serif'] = 'Helvetica'
cmap = plt.get_cmap('Pastel1')


compressor = {
    1:"blzpack_g",
    2:"bsc_g",
    3:"bzip2_g", 
    4:"GeCo3_g",
    5:"gzip_g",
    6:"JARVIS_g",
    7:"lizard_g",
    8:"lz4_g",
    9:"lzop_g",
    10:"mbgc_g",
    11:"MFCompress_g",
    12:"naf_g",
    13:"NUHT_g",
    14:"snzip_g",
    15:"zip_g",
    16:"xz_g",
    17:"zstd_g",
    18:"blzpack_p",
    19:"bsc_p",
    20:"bzip2_p",
    21:"gzip_p",
    22:"lizard_p",
    23:"lz4_p",
    24:"lzop_p", 
    25:"snzip_p", 
    26:"zip_p",
    27:"xz_p",
    28:"zstd_p" 
}





def warn(*args, **kwargs):
    pass
warnings.warn = warn

def concatenate_csv(args):
    # Open both CSV files in read mode
    with open(args.genome_filename, 'r') as file1, open(args.proteome_filename, 'r') as file2:
        # Read the contents of both files into separate variables
        reader1 = csv.reader(file1)
        reader2 = csv.reader(file2)
        combined_rows = []
        # Iterate over the rows of both lists
        for row1, row2 in zip(reader1, reader2):
            # Check if the first elements of the rows are the same
            if row1[0] == row2[0]:
                # Add the contents of the row to the combined rows list, removing the first element from row2
                combined_rows.append(row1 + row2[1:])
            else:
                break
        return combined_rows
       
def GetNumColumns(filepath):
    with open(filepath, 'r') as f:
        # Read the first line of the file
        first_line = f.readline()
        # Split the line by commas and return the length of the resulting list
        return len(first_line.split(','))

def flatten_columns(args, columns):
    if isinstance(columns, list):
    # columns is a list
        if isinstance(columns[0], list):
            genome_columns = columns[0]
            proteome_columns = columns[1]
        else:
            return columns
    num_genome_columns = GetNumColumns(args.genome_filename)
    # If genome_columns is an integer, wrap it in a list
    if isinstance(genome_columns, int):
        genome_columns = [genome_columns]
    # If proteome_columns is an integer, wrap it in a list
    if isinstance(proteome_columns, int):
        proteome_columns = [proteome_columns]
    # If either genome_columns or proteome_columns is an empty list, return an empty list
    if not genome_columns or not proteome_columns:
        return []
    return genome_columns + [i + num_genome_columns for i in proteome_columns]




def ReadData(args, columns):
    domains = {
        "viral": 0, 
        "bacteria": 1,
        "archaea": 2, 
        "fungi": 3,
        "protozoa": 4,
    }

    X_test, y_test = [], []

    # Call the concatenate_csv function and store the returned list of rows
    combined_rows = concatenate_csv(args)

    # Discard the first row (header)
    combined_rows = combined_rows[1:]

    # Flatten the columns list
    flattened_columns = flatten_columns(args,columns)
    # Create a list of columns to keep
    columns_to_keep = []
    for column in flattened_columns:
        # Check if any element in combined_rows at index i is empty
        if all(row[column] != '' for row in combined_rows):
            # If none of the elements are empty, append the index to columns_to_keep
            columns_to_keep.append(column)
    
    if not columns_to_keep:
            return None,None
    
    # Select the desired columns from the combined rows list
    selected_columns = [[row[i] for i in columns_to_keep] for row in combined_rows]
    # Iterate over the selected columns
    for row in selected_columns:
        tmp = []
        for value in row:
            tmp.append(float(value))
        X_test.append(tmp)
    
    y_test = [domains[row[0]] for row in combined_rows]
    
    return np.array(X_test), np.array(y_test), columns_to_keep

def Classify(args, columns):
    domains = ["Viral", "Bacteria", "Archaea", "Fungi", "Protozoa"]
    accuracy_XGB = []
    f1score_XGB = []

    # Flatten the columns list
    columns = flatten_columns(args,columns)

    data, labels, _ = ReadData(args, columns)
    # Check if data and labels are empty
    if data is None:
        # If they are empty, skip the classification for this iteration
        return
    if args.features_selection:
        clf = ExtraTreesClassifier(n_estimators=50)
        clf = clf.fit(data, labels)
        model = SelectFromModel(clf, prefit=True)
        print(data.shape)
        data = model.transform(data)
        print(data.shape)

    for a in range(numIterations):
        X_train, X_test, y_train, y_test = train_test_split(data, labels, test_size=0.20, stratify=labels, random_state=a)
        model = XGBClassifier(max_depth=12, learning_rate=0.89, n_estimators=500, eval_metric='mlogloss')
        model.fit(X_train, y_train)
        y_pred = model.predict(X_test)
        predictions = [round(value) for value in y_pred]
        accuracy_XGB.append(accuracy_score(y_test, predictions))
        f1score_XGB.append(f1_score(y_test, y_pred, average='weighted'))
        if args.classification_report:
            print("Classification report, using:", end=" ")
            print(" ".join([compressor[x] for x in columns]))
            print(classification_report(y_test, y_pred, target_names=domains, digits=4))
            break

    if args.accuracy:
        print("Accuracy of XGB, using:", end=" ")
        print(" ".join([compressor[x] for x in columns]))
        print(sum(accuracy_XGB)/len(accuracy_XGB))

    elif args.f1_score:
        print("F1 score of XGB, using:", end=" ")
        print(" ".join([compressor[x] for x in columns]))
        print(sum(f1score_XGB)/len(f1score_XGB))
    
    elif args.both:
        print("Accuracy of XGB, using:", end=" ")
        print(" ".join([compressor[x] for x in columns]))
        print(sum(accuracy_XGB)/len(accuracy_XGB))
        print("F1 score of XGB, using:", end=" ")
        print(" ".join([compressor[x] for x in columns]))
        print(sum(f1score_XGB)/len(f1score_XGB))
    print()

def ShapleyValue(args, columns):
    domains = ["Viral", "Bacteria", "Archaea", "Fungi", "Protozoa"]


    # Flatten the columns list
    columns = flatten_columns(args,columns)

    data, labels, selected_columns = ReadData(args, columns)
    # Check if data and labels are empty
    if data is None:
        # If they are empty, skip the classification for this iteration
        return
    if args.features_selection:
        clf = ExtraTreesClassifier(n_estimators=50)
        clf = clf.fit(data, labels)
        model = SelectFromModel(clf, prefit=True)
        data = model.transform(data)

    X_train, X_test, y_train, y_test = train_test_split(data, labels, test_size=0.20, stratify=labels, random_state=numIterations)
    model = XGBClassifier(max_depth=12, learning_rate=0.89, n_estimators=500, eval_metric='mlogloss')   
    model.fit(X_train, y_train)

    # SHAP analysis
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X_train)

    feature_names= [compressor[x] for x in selected_columns]
    feature_names = [value.replace("_g", " genome").replace("_p", " proteome") for value in feature_names]

    InterpretShapResults(shap_values, feature_names)

    df = pd.DataFrame(X_train, columns=feature_names) 
    fig, ax = plt.subplots()
    shap.summary_plot(shap_values, df, feature_names=feature_names, class_names=domains, plot_type='bar',show=False,color=cmap)

    # Adjust tick label size and weight
    ax.tick_params(axis='both', which='major', labelsize=8)

    # Adjust legend font size
    legend = ax.legend()
    for text in legend.get_texts():
        text.set_fontsize(10)

    # Adjust title size and weight
    ax.title.set_fontsize(10)
    ax.title.set_fontweight('bold')

    plt.savefig(SHAP_PLOT_PATH, bbox_inches='tight')
    plt.close()  # Close the plot to free up memory

    y_pred = model.predict(X_test)
    predictions = [round(value) for value in y_pred]
    print(accuracy_score(y_test, predictions))
    print(f1_score(y_test, y_pred, average='weighted'))

def InterpretShapResults(shap_values, feature_names):
     # If it's a multiclass classification, average the shap_values across all classes
    if len(np.array(shap_values).shape) == 3:
        shap_values = np.mean(shap_values, axis=0)
    
    # Calculate average absolute Shapley values
    mean_shap_values = np.abs(shap_values).mean(axis=0)
    feature_importance = pd.Series(mean_shap_values, index=feature_names).sort_values(ascending=False)
    
    # Display the average absolute Shapley values
    print("Average Absolute Shapley Values for Features:\n")
    print(feature_importance, "\n")
    
    # Plot ranked feature importances
    plt.figure()
    ax = feature_importance.plot(kind='bar', color='skyblue')
    plt.title("Feature Importance Ranked by Mean Absolute Shapley Value")
    plt.ylabel("Mean Absolute Shapley Value")
    plt.xlabel("Features")
    
    # Annotate each bar with the corresponding average absolute Shapley value
    for i, v in enumerate(feature_importance):
        ax.text(i, v + 0.01, round(v, 2), ha='center', va='bottom', fontsize=8)

    plt.tight_layout()
    plt.savefig(SHAP_PLOT_PATH_2, bbox_inches='tight')
    plt.close()  # Close the plot to free up memory

    # Provide descriptive statistics
    shap_df = pd.DataFrame(shap_values, columns=feature_names)
    print("\nDescriptive Statistics of Shapley Values for Features:\n")
    print(shap_df.describe())
    sys.exit()

def help(show=False):
    parser = argparse.ArgumentParser(description="")
    helper = parser.add_argument_group('System settings', 'System parameters to run the classifier in the different modes')
    helper.add_argument('-g', '--genomeFilename', dest='genome_filename', \
                        type=str, default=genomeFeaturesFilePath, \
                        help=f'The system settings file (default: {genomeFeaturesFilePath})')
    helper.add_argument('-p', '--proteomeFilename', dest='proteome_filename', \
                        type=str, default=proteomeFeaturesFilePath, \
                        help=f'The system settings file (default: {proteomeFeaturesFilePath})')     
    helper.add_argument('-f1', '--f1-score', default=False, action='store_true', \
                            help='This flag produces the classificarion report using the F1-score (default: False)')
    helper.add_argument('-a', '--accuracy', default=False, action='store_true', \
                            help='This flag produces the classificarion report using the Accuracy metric (default: False)')
    helper.add_argument('-b', '--both', default=False, action='store_true', \
                            help='This flag produces the classificarion report using the both metrics (default: False)') 
    helper.add_argument('-fs', '--features-selection', default=False, action='store_true', \
                            help='This flag performs feature selection (default: False)') 
    helper.add_argument('-ac', '--all-columns', default=False, action='store_true', \
                            help='This flag classifies using all features (default: False)') 
    helper.add_argument('-cr', '--classification-report', default=False, action='store_true', \
                            help='This flag generates the classification report (default: False)') 
    helper.add_argument('-bf', '--brute-force', default=False, action='store_true', \
                            help='This flag performs brute force classification of all possible combination of features (default: False)') 
    helper.add_argument('-ag', '--all-genome', default=False, action='store_true', \
                            help='This flag performs brute force classification of all possible combination of features for the genome (default: False)') 
    helper.add_argument('-ap', '--all-proteome', default=False, action='store_true', \
                            help='This flag performs brute force classification of all possible combination of features for the proteome (default: False)') 
    
    if show:
        parser.print_help()
    return parser.parse_args()
    

if __name__ == "__main__":
    
    args = help()
    if args.accuracy or args.f1_score or args.both or args.classification_report:
        if args.all_columns:
            Classify(args, [list(range(1,18,1)),list(range(1,11))])
            ShapleyValue(args, [list(range(1,18,1)),list(range(1,11))])
        elif args.all_genome:
            Classify(args, list(range(1,18,1)))
        elif args.all_proteome:
            Classify(args, list(range(18,29)))
        elif args.brute_force:
            all_comb_list=[]
            for x in range(1,29,1):
                com_list = list(combinations(range(1,29), x+1))
                [Classify(args,list(ele)) for ele in com_list]
        else:
            for column in range(1,29):
                Classify(args, [column])
    else:
        help(True)