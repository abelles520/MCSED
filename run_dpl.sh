#!/bin/bash



echo 'SFH = dpl, updated bounds'

echo 'z=0.0016'
python run_mcsed_fit.py -p -f bin_0.0016.txt -o dpl_0.0016.out -z 0.0016 -sfh double_powerlaw -dl noll
echo 'z=0.0025'
python run_mcsed_fit.py -p -f bin_0.0025.txt -o dpl_0.0025.out -z 0.0025 -sfh double_powerlaw -dl noll
echo 'z=0.0039'
python run_mcsed_fit.py -p -f bin_0.0039.txt -o dpl_0.0039.out -z 0.0039 -sfh double_powerlaw -dl noll
echo 'z=0.0061'
python run_mcsed_fit.py -p -f bin_0.0061.txt -o dpl_0.0061.out -z 0.0061 -sfh double_powerlaw -dl noll
echo 'z=0.015'
python run_mcsed_fit.py -p -f bin_0.015.txt -o dpl_0.015.out -z 0.015 -sfh double_powerlaw -dl noll
echo 'z=0.019'
python run_mcsed_fit.py -p -f bin_0.019.txt -o dpl_0.019.out -z 0.019 -sfh double_powerlaw -dl noll
echo 'z=0.024'
python run_mcsed_fit.py -p -f bin_0.024.txt -o dpl_0.024.out -z 0.024 -sfh double_powerlaw -dl noll
echo 'z=0.03'
python run_mcsed_fit.py -p -f bin_0.03.txt -o dpl_0.03.out -z 0.03 -sfh double_powerlaw -dl noll
