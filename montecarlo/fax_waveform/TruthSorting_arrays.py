###########################
## Code for sorting the truth root file(peak-by-peak) format into event-by-event format
## Output is a pickle file
## by Qing Lin
#########
## @ 2017-01-09
###########################


import pickle 
import pandas as pd

import ROOT
from ROOT import TFile
from ROOT import TTree

import root_pandas

import sys



if len(sys.argv)<2:
    print("============= Syntax =============")
    print("python TruthSorting_arrays.py <truth file.csv (abs.)> <output file (no ext)> <output format; 0=pickle (default), 1=ROOT, 2=both> <(opt.) save afterpulses (default 0)>")
    exit()


TruthFile = sys.argv[1]
OutputFile = sys.argv[2]
if '.root' in OutputFile:
    OutputFile = OutputFile.split('.root')[0]
else:
    OutputFile = OutputFile.split('.pkl')[0]
OutputFormat=0
if len(sys.argv)>3:
    OutputFormat = float(sys.argv[3])

save_ap = 0
if len(sys.argv)>4:
    save_ap = sys.argv[4]

print ("Input file: ", TruthFile)

###################
## need to sort and add the truth peak values into Data as well
## peak values are added as arrays with len() = # of peaks
## s1 peaks get nans for s2-only values
####################
Data = {}


# load the truth data from csv
truth_data = pd.read_csv(TruthFile)
NumStepsInTruth = len(truth_data.index)

# initialize Data for truth 
event_keys = ['index_truth', 'peaks_length']
s1s2_keys = ['time_truth', 'time_std_truth', 'time_last_photon_truth', 'time_interaction_truth', 'area_truth', 'type_truth', 'x_truth', 'y_truth', 'z_truth', 'top_fraction']
s2_only_keys = ['electron_time_truth', 'first_electron_time_truth', 'last_electron_time_truth']

for field in (event_keys + s1s2_keys + s2_only_keys):
    Data[field] = []

iteration_id = 0
for event_id in range(10000000):
    if iteration_id>=NumStepsInTruth:
        break
    if (event_id+1)%100==0:
        print("==== processed_file: "+str(event_id+1)+" events finished loading")

    result = {}
    for field in event_keys:
        result[field] = -1
    for field in (s1s2_keys + s2_only_keys):
        result[field] = []

    ifcounteds1 = 0
        
    while truth_data['event'][iteration_id]==event_id:
        tag = 2 # 0 for s1, 1 for s2, 2 for photoionization
        if truth_data['peak_type'][iteration_id] == 's1':
            tag = 0
        if truth_data['peak_type'][iteration_id] == 's2':
            tag = 1

        # fill these fields either way
        if save_ap or (tag!=2):
            result['time_truth'].append(truth_data['t_mean_photons'][iteration_id])
            result['time_std_truth'].append(truth_data['t_sigma_photons'][iteration_id])
            result['time_last_photon_truth'].append(truth_data['t_last_photon'][iteration_id])
            result['time_interaction_truth'].append(truth_data['t_interaction'][iteration_id])
            result['area_truth'].append(truth_data['n_photons'][iteration_id])
            result['type_truth'].append(tag + 1) # 1 for s1, 2 for s2, 3 for photoionization
            result['x_truth'].append(truth_data['x'][iteration_id])
            result['y_truth'].append(truth_data['y'][iteration_id])
            result['z_truth'].append(truth_data['z'][iteration_id])
            result['top_fraction'].append(truth_data['top_fraction'][iteration_id])

        if (tag==1):
            # peak is an S2
            result['electron_time_truth'].append(truth_data['t_mean_electrons'][iteration_id])
            result['first_electron_time_truth'].append(truth_data['t_first_electron'][iteration_id])
            result['last_electron_time_truth'].append(truth_data['t_last_electron'][iteration_id])
        elif (tag==0) or save_ap:
            # peak is not an s2
            for s2_field in s2_only_keys:
                result[s2_field].append(float('nan'))
        iteration_id += 1
        if iteration_id>=NumStepsInTruth:
            break
    result['index_truth'] = event_id
    result['peaks_length'] = len(result['area_truth'])
    #for field in list(Data.keys()):
    for field in list(Data.keys()):
        Data[field].append(result[field])
    

print ("Number of events: ", event_id)

######################
## Convert to data format in pandas
######################
df = pd.DataFrame(Data)

#######################
## Save to ROOT
#######################


def is_array_field(test_dataframe, test_field):
    """Tests if the column test_field in test_dataframe is an array field
    :param test_dataframe: dataframe to test
    :param test_field: column name to test
    :return: True or False
    """
    if test_dataframe.empty:
        raise ValueError("No data saved from dataset - DataFrame is empty")
    test_value = test_dataframe[test_field][0]
    return (hasattr(test_value, "__len__") and not isinstance(test_value, (str, bytes)))


def dataframe_to_root(dataframe, root_filename, treename='tree', mode='recreate'):
    branches = {}
    branch_types = {}

    single_value_keys = []
    array_keys = []
    array_root_file = ROOT.TFile(root_filename, mode)
    datatree = ROOT.TTree(treename, "")

    # setting up branches
    for branch_name in dataframe.columns:
        if is_array_field(dataframe, branch_name):
            # This is an array field. Find or create its 'length branch',
            # needed for saving the array to root (why exactly? Wouldn't a vector work?)
            length_branch_name = 'peaks_length'
            if not length_branch_name in dataframe.columns:
                dataframe[length_branch_name] = np.array([len(x) for x in dataframe[branch_name]], dtype=np.int64)
                single_value_keys.append(length_branch_name)
                branches[length_branch_name] = np.array([0])
                branch_types[length_branch_name] = 'L'
            max_length = dataframe[length_branch_name].max()
            first_element_index = next((index for index, branch_length in enumerate(dataframe[length_branch_name]) if branch_length), None)
            first_element = dataframe[branch_name][first_element_index][0]
            array_keys.append(branch_name)

        else:
            # Ordinary scalar field
            max_length = 1
            first_element = dataframe[branch_name][0]
            single_value_keys.append(branch_name)

        # setting branch types
        if isinstance(first_element, (int, np.integer)):
            branch_type = 'L'
            branches[branch_name] = np.zeros(max_length, dtype=np.int64)
        elif isinstance(first_element, (float, np.float)):
            branch_type = 'D'
            branches[branch_name] = np.zeros(max_length, dtype=np.float64)
        else:
            raise TypeError('Branches must contain ints, floats, or arrays of ints or floats' )
        branch_types[branch_name] = branch_type

    # creating branches
    for single_value_key in single_value_keys:
        datatree.Branch(single_value_key, branches[single_value_key],
                        "%s/%s" % (single_value_key, branch_types[single_value_key]))
    for array_key in array_keys:
        assert 'peaks_length' in dataframe.columns
        datatree.Branch(array_key, branches[array_key],
                        "%s[%s]/%s" % (array_key, 'peaks_length', branch_types[array_key]))

    # filling tree
    for event_index in range(len(dataframe.index)):
        for single_value_key in single_value_keys:
            branches[single_value_key][0] = dataframe[single_value_key][event_index]
        for array_key in array_keys:
            branches[array_key][:len(dataframe[array_key][event_index])] = dataframe[array_key][event_index]
        datatree.Fill()
    array_root_file.Write()
    array_root_file.Close()


if OutputFormat == 1 or OutputFormat == 2:
    # stuff is imported here and function is used to allow root w/ arrays
    # this adds some time, so default output is pkl
    import numpy as np
    import ROOT
    dataframe_to_root(df, OutputFile + ".root", treename='fax_truth_sort')
    print ("Written to: ", OutputFile+".root")


#######################
## Save to pickle
#######################
if OutputFormat == 0 or OutputFormat == 2:
    df.to_pickle(OutputFile + '.pkl')
    print ("Written to: ", OutputFile+".pkl")

