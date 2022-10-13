'''
Hosts the Dscsm class. That class is the simulation environment, so per each
Dscsm instance there's a directory where all the necesary files to run the model
are allocated. To run the model there are 3 basic steps:
    1. Create a new Dscsm instance.
    2. Initialize the environment by running the setup() method.
    3. Run the model by running the run() method.
You can close the simulation environment by running the close() method.

Example
-------
    >>> # Create random weather data
    >>> df = pd.DataFrame(
        {
        'tn': np.random.gamma(10, 1, N),
        'rad': np.random.gamma(10, 1.5, N),
        'prec': np.round(np.random.gamma(.4, 10, N), 1),
        'rh': 100 * np.random.beta(1.5, 1.15, N),
        },
        index=DATES,
    )
    >>> df['TMAX'] = df.tn + np.random.gamma(5., .5, N)
    >>> # Create a WeatherData instance
    >>> WTH_DATA = WeatherData(
        df,
        variables={
            'tn': 'TMIN', 'TMAX': 'TMAX',
            'prec': 'RAIN', 'rad': 'SRAD',
            'rh': 'RHUM'
        }
    )
    >>> # Create a WheaterStation instance
    >>> wth = WeatherStation(
        WTH_DATA, 
        {'ELEV': 33, 'LAT': 0, 'LON': 0, 'INSI': 'dpoes'}
    )
    >>> # Initialize soil, crop and management instances.
    >>> soil = SoilProfile(default_class='SIL')
    >>> crop = Crop('maize')
    >>> man = Management(
        cultivar='IB0001',
        planting_date=DATES[10],
    )
    >>> man.harvest_details['table'].loc[0, ['HDATE', 'HPC']] = \
        [DATES[190].strftime('%y%j'), 100]
    >>> # Initialize Dscsm instance and run.
    >>> dssat = Dscsm()
    >>> dssat.setup(cwd='/tmp/dssattest')
    >>> dssat.run(
        soil=soil, weather=wth, crop=crop, management=man,
    )
    >>> # Get output
    >>> PlantGro = dssat.outputs['PlantGro']
    >>> dssat.close() # Terminate the simulation environment
'''

import subprocess
import shutil
import os
import tempfile    
import random
import string
import pandas as pd

# Libraries for second version
import DSSATTools
from DSSATTools.soil import SoilProfile
from DSSATTools.weather import WeatherStation
from DSSATTools.crop import Crop
from DSSATTools.management import Management
from DSSATTools.base.sections import TabularSubsection, RowBasedSection


OUTPUTS = ['PlantGro', ]

class Dscsm():
    # TODO: Class implementation must allow to change Crop, Weather, Experiment(Management) and Soil. So, each of this must be defined as instances, and this class must keep track of those changes, so as to create new files only if the instance has changed.

    # TODO: Each crop model has to have it's own class. So far, I'll implement only CERES-MAIZE.

    # TODO: An option to run without definen input instances has to be implement as well. This will allow to use the class if the model is not implemented yet. For this case, the input will be initialized as a path (str) and not as an instance. 

    def __init__(self):
        '''
        
        '''
        BASE_PATH = os.path.dirname(DSSATTools.__file__)
        self._STATIC_PATH = os.path.join(BASE_PATH, 'static')
        self._BIN_PATH = os.path.join(self._STATIC_PATH, 'bin', 'dscsm048')
        self._STD_PATH = os.path.join(self._STATIC_PATH, 'StandardData')
        self._CRD_PATH = os.path.join(self._STATIC_PATH, 'Genotype')
        self._SLD_PATH = os.path.join(self._STATIC_PATH, 'Soil')

        self._SETUP = False
        self._input = {
            'crop': None, 'wheater': None, 'soil': None, 'management': None 
        }

        self.output = {} # TODO: Implement an output class.There'll be a basic one, andvariations with models.
        self.OUTPUT_LIST = OUTPUTS

    def setup(self, cwd=None, overwrite=False, **kwargs):
        '''
        Setup a simulation environment.
        Creates a tmp folder to run the simulations and move all the required
        files to run the model. Some rguments are optional, if those aren't provided,
        then standard files location will be used.

        Arguments
        ----------
        cwd: str
            Working directory. All the model files would be moved to that directory.
            If None, then a tmp directory will be created and then removed.
        overwrite: bool
            Whether to overwrite or not the current simulation environment. If
            true, then a new simulation environment will be created, and all the 
            outputs and inputs will be reseted.
        '''
        #
        # Create wd if it doesn't exist and move files to it.
        #
        # TODO: Check if this instance was already set-up. If it was, then stop, show warning, and ask to run the method with overwrite=True
        TMP_BASE = tempfile.gettempdir()
        if cwd:
            self._RUN_PATH = cwd
            if not os.path.exists(self._RUN_PATH):
                os.mkdir(self._RUN_PATH)
        else:
            self._RUN_PATH = os.path.join(
                TMP_BASE, 
                ''.join(random.choices(string.ascii_lowercase, k=8))
            )
            os.mkdir(self._RUN_PATH)
        
        # Move files
        if not os.path.exists(
            os.path.join(self._RUN_PATH, os.path.basename(self._BIN_PATH))
            ):
            shutil.copyfile(
                self._BIN_PATH, 
                os.path.join(self._RUN_PATH, os.path.basename(self._BIN_PATH))
            )
            os.chmod(
                os.path.join(self._RUN_PATH, os.path.basename(self._BIN_PATH)),
                mode=111
            )
        for file in os.listdir(self._STATIC_PATH):
            if file.endswith('.CDE'):
                shutil.copyfile(
                    os.path.join(self._STATIC_PATH, file), 
                    os.path.join(self._RUN_PATH, file)
                )
        self._SETUP = True


    def run(self, 
            soil:SoilProfile,
            weather:WeatherStation,
            crop:Crop,
            management:Management,
        ):
        '''
        Start the simulation and runs until the end or failure.

        Arguments
        ----------
        soil: DSSATTools.soil.Soil
            SoilProfile instance
        weather: DSSATTools.weather.WeatherStation
            WeatherStation instance
        crop: DSSATTools.crop.Crop
            Crop instance
        managment: DSSATTools.management.Management
            Management instance
        '''
        
        assert self._SETUP, 'You must initialize the simulation environment by'\
            + ' running the setup() method'

        # Remove previous outputs
        OUTPUT_FILES = [i for i in os.listdir(self._RUN_PATH) if i[-3:] == 'OUT']
        for file in OUTPUT_FILES:
            os.remove(os.path.join(self._RUN_PATH, file))
        # Fill Managament fields
        management.cultivars['CR'] = crop.CODE
        management.cultivars['CNAME'] = \
            crop.cultivar[management.cultivar]['VRNAME..........']

        management.fields['WSTA....'] = weather.INSI \
            + management.sim_start.strftime('%y%m')
        management.fields['SLDP'] = soil.total_depth
        management.fields['ID_SOIL'] = soil.id

        management.initial_conditions['PCR'] = crop.CODE
        if not management.initial_conditions['ICDAT']:
            management.initial_conditions['ICDAT'] = \
                management.sim_start.strftime('%y%j')
        
        initial_swc = []
        for depth, layer in soil.layers.items():
            initial_swc.append((
                depth, 
                layer['SLLL'] + management.initial_swc \
                    * (layer['SDUL'] - layer['SLLL'])
            ))
        table = TabularSubsection(initial_swc)
        table.columns = ['ICBL', 'SH2O']
        table = table.sort_values(by='ICBL').reset_index(drop=True)
        table['SNH4'] = [0.]*len(table)
        table['SNO3'] = [1.] + [0.]*(len(table)-1)
        management.initial_conditions['table'] = table

        management.simulation_controls['SMODEL'] = crop.SMODEL        

        management_filename = weather.INSI \
            + management.sim_start.strftime('%y%m') \
            + f'.{crop.CODE}X'
        management_filename = os.path.join(self._RUN_PATH, management_filename) 
        management.write(filename=management_filename)
        crop.write(self._RUN_PATH)
        soil.write(os.path.join(self._RUN_PATH, 'SOIL.SOL'))
        wth_path = os.path.join(self._RUN_PATH, 'Weather')
        weather.write(wth_path)

        with open(os.path.join(self._RUN_PATH, 'DSSATPRO.L48'), 'w') as f:
            f.write(f'WED    {wth_path}\n')
            f.write(f'MMZ    {self._RUN_PATH} dscsm048 MZCER048\n')
            f.write(f'CRD    {self._CRD_PATH}\n')
            f.write(f'PSD    {os.path.join(self._STATIC_PATH, "Pest")}\n')
            f.write(f'SLD    {self._SLD_PATH}\n')
            f.write(f'STD    {self._STD_PATH}\n')

        # Run it
        excinfo = subprocess.run(
            [self._BIN_PATH, 'C', os.path.basename(management_filename), '1'], 
            cwd=self._RUN_PATH
        )

        assert excinfo.returncode == 0, 'DSSAT execution Failed, check '\
            + f'{os.path.join(self._RUN_PATH, "ERROR.OUT")} file for a'\
            + ' detailed report'

        # TODO: Read outputs.
        OUTPUT_FILES = [i for i in os.listdir(self._RUN_PATH) if i[-3:] == 'OUT']
        
        for file in self.OUTPUT_LIST:
            assert f'{file}.OUT' in OUTPUT_FILES, \
                f'{file}.OUT does not exist in {self._RUN_PATH}'
            df = pd.read_csv(
                os.path.join(self._RUN_PATH, f'{file}.OUT'),
                skiprows=5, sep=' ', skipinitialspace=True
            )
            if all(('@YEAR' in df.columns, 'DOY' in df.columns)):
                df.index = pd.to_datetime(
                    (df['@YEAR'] + df['DOY']).map(lambda x: f'{x:05d}'),
                    format='%y%j'
                )
            self.output[file] = df
        return

    def close(self):
        '''
        Remove all the files in the run path.
        '''
        shutil.rmtree(self._RUN_PATH)
    

