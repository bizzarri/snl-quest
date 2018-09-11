from __future__ import absolute_import
import logging
import os
import json

import pandas as pd

from es_gui.tools.dms import DataManagementSystem
from es_gui.tools.valuation.utilities import *


class ValuationDMS(DataManagementSystem):
    """
    A class for managing data for the energy storage valuation optimization functions. Class methods for each type of file to be loaded are included, extending from the get_data() method of the superclass. Each of these methods uses get_data() to retrieve the relevant data and loads the file and adds it to the DMS if the data is not loaded. An optional class method for calling each of the individual data methods can be included to, e.g., form the necessary arguments and return the desired variables.

    :param home_path: A string indicating the relative path to where data is saved.
    """
    def __init__(self, home_path, **kwargs):
        DataManagementSystem.__init__(self, **kwargs)

        self.home_path = home_path

        with open(os.path.abspath(os.path.join(self.home_path, '..', 'es_gui', 'apps', 'valuation', 'definitions', 'nodes.json')), 'r') as fp:
            self.NODES = json.load(fp)

        #self.node_names = pd.read_excel(self.home_path+'nodeid.xlsx', sheetname=None)
        self.delimiter = ' @ '  # delimiter used to split information in id_key

    def get_node_name(self, node_id, ISO):
        """
        Retrieves the node name corresponding to the given node_id using the lookup table loaded during initialization.
        :param node_id: A string or int of a node ID.
        :return: The corresponding node name as a string.
        """
        # TODO: map node_id to node name

        return str(node_id)

        # try:
        #     node_name = self.NODES[ISO][node_id]['name']
        # except KeyError as e:
        #     raise e
        # else:
        #     return node_name

    def get_ercot_spp_data(self, id_key):
        """Retrieves DAM-SPP data for ERCOT."""
        logging.info('DMS: Loading ERCOT DA-SPP')
        try:
            # attempt to access data if it is already loaded
            spp_da = self.get_data(id_key)
            logging.info('DMS: Data located in DMS, retrieving...')
        except KeyError:
            # load the data and add it to the DMS
            logging.info('DMS: Data not yet in DMS, loading...')

            # deconstruct id_key to obtain args for read function
            spp_da = read_ercot_da_spp(*id_key.split(self.delimiter))
            self.add_data(spp_da, id_key)
        finally:
            return spp_da

    def get_ercot_ccp_data(self, id_key):
        """Retrieves DAM-CCP data for ERCOT."""
        logging.info('DMS: Loading ERCOT DA-CCP')
        try:
            # attempt to access data if it is already loaded
            REGUP = self.get_data(id_key + self.delimiter + 'REGUP')
            REGDN = self.get_data(id_key + self.delimiter + 'REGDN')
            logging.info('DMS: Data located in DMS, loading...')
        except KeyError:
            # load the data and add it to the DMS
            logging.info('DMS: Data not yet in DMS, loading...')

            # deconstruct id_key to obtain args for read function
            REGDN, REGUP = read_ercot_da_ccp(*id_key.split(self.delimiter)[:2])

            self.add_data(REGUP, id_key + self.delimiter + 'REGUP')
            self.add_data(REGDN, id_key + self.delimiter + 'REGDN')
        finally:
            return REGDN, REGUP

    def get_ercot_data(self, year, month, settlement_point):
        # construct file name paths
        path = os.path.join(self.home_path, 'ERCOT')  # path to data_bank root

        if isinstance(month, int):
            month = str(month)

        spp_fpath = os.path.join(path, 'SPP', str(year))
        
        try:
            for filename in os.listdir(spp_fpath):
                if filename.lower().endswith('.xlsx'):
                    fname = filename
        except ValueError as e:
            raise(e)

        spp_fname = os.path.join(spp_fpath, fname)

        ccp_fpath = os.path.join(path, 'CCP', str(year))

        try:
            for filename in os.listdir(ccp_fpath):
                if filename.lower().endswith('.csv'):
                    fname = filename
        except ValueError as e:
            raise(e)

        ccp_fname = os.path.join(ccp_fpath, fname)

        # construct identifier keys
        spp_id = self.delimiter.join([spp_fname, month, settlement_point])
        ccp_id = self.delimiter.join([ccp_fname, month])

        # retrieve data
        spp_da = self.get_ercot_spp_data(spp_id)
        rd, ru = self.get_ercot_ccp_data(ccp_id)

        return spp_da, rd, ru

    def get_pjm_lmp_data(self, *args):
        """Deprecated since 1.0"""
        logging.info('DMS: Loading PJM DA-LMP')
        try:
            # attempt to access data if it is already loaded
            lmp_da = self.get_data(*args)
            logging.info('DMS: Data located in DMS, retrieving...')
        except KeyError:
            # load the data and add it to the DMS
            logging.info('DMS: Data not yet in DMS, loading...')
            lmp_da = read_pjm_da_lmp(*args)
            self.add_data(lmp_da, *args)
        finally:
            return lmp_da

    def get_pjm_reg_price_data(self, *args):
        """Deprecated since 1.0"""
        logging.info('DMS: Loading PJM regulation prices')
        try:
            # attempt to access data if it is already loaded
            RegCCP = self.get_data(*args+('RegCCP',))
            RegPCP = self.get_data(*args+('RegPCP',))
            logging.info('DMS: Data located in DMS, retrieving...')
        except KeyError:
            # load the data and add it to the DMS
            logging.info('DMS: Data not yet in DMS, loading...')
            RegCCP, RegPCP = read_pjm_reg_price(*args)
            self.add_data({'RegCCP': RegCCP, 'RegPCP': RegPCP}, *args)
        finally:
            return RegCCP, RegPCP

    def get_pjm_mileage_data(self, *args):
        """Deprecated since 1.0"""
        logging.info('DMS: Loading PJM mileage data')
        try:
            # attempt to access data if it is already loaded
            MR = self.get_data(*args+('MR',))
            RA = self.get_data(*args+('RA',))
            RD = self.get_data(*args+('RD',))
            logging.info('DMS: Data located in DMS, retrieving...')
        except KeyError:
            # load the data and add it to the DMS
            logging.info('DMS: Data not yet in DMS, loading...')
            MR, RA, RD = read_pjm_mileage(*args)
            self.add_data({'MR': MR, 'RA': RA, 'RD': RD}, *args)
        finally:
            return MR, RA, RD

    def get_pjm_reg_signal_data(self, *args):
        """Deprecated since 1.0"""
        logging.info('DMS: Loading PJM regulation signal')
        try:
            # attempt to access data if it is already loaded
            RUP = self.get_data(*args+('RegUp',))
            RDW = self.get_data(*args+('RegDown',))
            logging.info('DMS: Data located in DMS, retrieving...')
        except KeyError:
            # load the data and add it to the DMS
            logging.info('DMS: Data not yet in DMS, loading...')
            RUP, RDW = read_pjm_reg_signal(*args)
            self.add_data({'RegUp': RUP, 'RegDown': RDW}, *args)
        finally:
            return RUP, RDW

    def get_pjm_data(self, year, month, nodeid):
        path = os.path.join(self.home_path, 'PJM')
        
        nodeid = str(nodeid)
        year = str(year)
        month = str(month)

        lmp_key = self.delimiter.join([path, year, month, nodeid, 'SPP'])
        mr_key = self.delimiter.join([path, year, month, 'MR'])
        ra_key = self.delimiter.join([path, year, month, 'RA'])
        rd_key = self.delimiter.join([path, year, month, 'RD'])
        rccp_key = self.delimiter.join([path, year, month, 'RegCCP'])
        rpcp_key = self.delimiter.join([path, year, month, 'RegPCP'])

        try:
            # attempt to access data if it is already loaded
            lmp_da = self.get_data(lmp_key)
            MR = self.get_data(mr_key)
            RA = self.get_data(ra_key)
            RD = self.get_data(rd_key)
            RegCCP = self.get_data(rccp_key)
            RegPCP = self.get_data(rpcp_key)
        except KeyError:
            # load the data and add it to the DMS
            logging.info('DMS: Data not yet in DMS, loading...')
            lmp_da, MR, RA, RD, RegCCP, RegPCP = read_pjm_data(path, year, month, nodeid)

            self.add_data(lmp_da, lmp_key)
            self.add_data(MR, mr_key)
            self.add_data(RA, ra_key)
            self.add_data(RD, rd_key)
            self.add_data(RegCCP, rccp_key)
            self.add_data(RegPCP, rpcp_key)

        return lmp_da, MR, RA, RD, RegCCP, RegPCP
    
    def get_miso_lmp_data(self, *args):
        """Deprecated since 1.0"""
        logging.info('DMS: Loading MISO DA-LMP')
        try:
            # attempt to access data if is already loaded
            lmp_da = self.get_data(*args)
            logging.info('DMS: Data located in DMS, retrieving...')
        except KeyError:
            # load the data and add it to the DMS
            logging.info('DMS: Data not yet in DMS, loading...')
            lmp_da = read_miso_da_lmp(*args)
            self.add_data(lmp_da, *args)
        finally:
            return lmp_da

    def get_miso_reg_data(self, *args):
        """Deprecated since 1.0"""
        logging.info('DMS: Loading MISO RegMCP')
        try:
            # attempt to access data if is already loaded
            RegMCP = self.get_data(*args)
            logging.info('DMS: Data located in DMS, retrieving...')
        except KeyError:
            # load the data and add it to the DMS
            logging.info('DMS: Data not yet in DMS, loading...')
            RegMCP = read_miso_reg_price(*args)
            self.add_data(RegMCP, *args)
        finally:
            return RegMCP

    def get_miso_data(self, year, month, nodeid):
        path = os.path.join(self.home_path, 'MISO')

        year = str(year)
        month = str(month)

        lmp_key = self.delimiter.join([path, year, month, nodeid, 'LMP'])
        regmcp_key = self.delimiter.join([path, year, month, 'MCP'])

        try:
            # attempt to access data if it is already loaded
            lmp_da = self.get_data(lmp_key)
            RegMCP = self.get_data(regmcp_key)
        except KeyError:
            # load the data and add it to the DMS
            logging.info('DMS: Data not yet in DMS, loading...')
            lmp_da, RegMCP = read_miso_data(path, year, month, nodeid)

            self.add_data(lmp_da, lmp_key)
            self.add_data(RegMCP, regmcp_key)

        return lmp_da, RegMCP

    def get_isone_data(self, year, month, nodeid):
        path = self.home_path + '/ISONE/'

        fnameLMP = "DA_node{0:s}_month{1:s}_year{2:s}.csv".format(nodeid, month, year)
        fnameREG = "REG_month{0:s}_year{1:s}.csv".format(month, year)

        # fname_path_LMP = path + "LMP/" + str(year) + "/" + str(month).zfill(2) + "/" + fnameLMP
        # fname_path_REG = path + "REG/" + str(year) + "/" + fnameREG

        # key_isone_LMP = "ISONE-" + "LMP-" + str(year) + "-" + str(month).zfill(2) + "-node" + str(nodeidi)
        # key_isone_REG = "ISONE-" + "REG-" + str(year) + "-" + str(month).zfill(2)
        key_isone_LMP = "ISONE-" + "LMP-" + year + "-" + month.zfill(2) + "-node" + nodeid
        key_isone_REG = "ISONE-" + "REG-" + year + "-" + month.zfill(2)


        logging.info('DMS: Loading ISO-NE LMP and Regulation Prices')
        try:
            # attempt to access data if it is already loaded
            # RegCCP = self.get_data(fname_path_REG,'RegCCP') # this works
            # RegPCP = self.get_data(fname_path_REG,'RegPCP') # this works
            # daLMP = self.get_data(fname_path_LMP) # this works

            key_isone_REG_CCP = key_isone_REG + "-CCP"
            key_isone_REG_PCP = key_isone_REG + "-PCP"

            RegCCP = self.get_data(key_isone_REG_CCP)
            RegPCP = self.get_data(key_isone_REG_PCP)
            daLMP = self.get_data(key_isone_LMP)

            logging.info('DMS: Data located in DMS, retrieving...')
        except KeyError:
            # load the data and add it to the DMS
            logging.info('DMS: Data not yet in DMS, loading...')
            # RegCCP, RegPCP = read_pjm_reg_price(*args) in utilities: -def read_pjm_reg_price(fname, month):

            yeari = int(year)
            monthi = int(month)
            nodeidi = int(nodeid)

            daLMP, RegCCP, RegPCP = read_isone_data(path, yeari, monthi, nodeidi) # in utilities: def read_isone_data(fpath, year, month, nodeid):

            # self.add_data(daLMP, fname_path_LMP) # this works

            self.add_data(daLMP, key_isone_LMP)  # this works

            # self.add_data(RegCCP, (fname_path_REG,'RegCCP'))
            # self.add_data(RegPCP, (fname_path_REG, 'RegPCP'))

            # self.add_data({'RegCCP': RegCCP, 'RegPCP': RegPCP}, fname_path_REG) # this works!

            key_isone_REG_CCP = key_isone_REG + "-CCP"
            key_isone_REG_PCP = key_isone_REG + "-PCP"
            self.add_data(RegCCP, key_isone_REG_CCP)
            self.add_data(RegPCP, key_isone_REG_PCP)
        finally:
            return daLMP, RegCCP, RegPCP


if __name__ == '__main__':
    dms = ValuationDMS(save_name='valuation_dms.p', home_path='data')
    
    # # ERCOT - data doesn't exist
    # year = 2010
    # month = 1
    # settlement_point = 'HB_HOUSTON'

    # spp_da, rd, ru = dms.get_ercot_data(year, month, settlement_point)

    # # ERCOT
    # year = 2010
    # month = 12
    # settlement_point = 'HB_HOUSTON'

    # spp_da, rd, ru = dms.get_ercot_data(year, month, settlement_point)

    # PJM
    # year = 2016
    # month = 5
    # nodeid = 1

    # lmp_da, MR, RA, RD, RegCCP, RegPCP = dms.get_pjm_data(year, month, nodeid)

    # MISO
    year = 2015
    month = 3
    nodeid = 'AEC'

    lmp_da, RegMCP = dms.get_miso_data(year, month, nodeid)