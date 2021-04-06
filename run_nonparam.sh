#!/bin/bash


echo 'SFH = nonparametric, updated bounds'

echo 'z=0.0016'
python run_mcsed_fit.py -p -f bin_0.0016.txt -o nonparam_0.0016.out -z 0.0016 -sfh binned_lsfr -dl noll
echo 'z=0.0025'
python run_mcsed_fit.py -p -f bin_0.0025.txt -o nonparam_0.0025.out -z 0.0025 -sfh binned_lsfr -dl noll
echo 'z=0.0039'
python run_mcsed_fit.py -p -f bin_0.0039.txt -o nonparam_0.0039.out -z 0.0039 -sfh binned_lsfr -dl noll
echo 'z=0.0061'
python run_mcsed_fit.py -p -f bin_0.0061.txt -o nonparam_0.0061.out -z 0.0061 -sfh binned_lsfr -dl noll
echo 'z=0.015'
python run_mcsed_fit.py -p -f bin_0.015.txt -o nonparam_0.015.out -z 0.015 -sfh binned_lsfr -dl noll
echo 'z=0.019'
python run_mcsed_fit.py -p -f bin_0.019.txt -o nonparam_0.019.out -z 0.019 -sfh binned_lsfr -dl noll
echo 'z=0.024'
python run_mcsed_fit.py -p -f bin_0.024.txt -o nonparam_0.024.out -z 0.024 -sfh binned_lsfr -dl noll
echo 'z=0.03'
python run_mcsed_fit.py -p -f bin_0.03.txt -o nonparam_0.03.out -z 0.03 -sfh binned_lsfr -dl noll

