#!/usr/bin/env python

"""
Data Aggregator for SAMS Software accounting
"""

from __future__ import print_function

from optparse import OptionParser
import logging
import sys

import sams.core

logger = logging.getLogger(__name__)

id = 'sams.aggregator'

class Main:

    def __init__(self):
        # Options
        parser = OptionParser()
        parser.add_option("--config", type="string", action="store", dest="config", default="/etc/sams/sams-aggregator.yaml", help="Config file [%default]")
        parser.add_option("--logfile", type="string", action="store", dest="logfile", help="Log file")
        parser.add_option("--loglevel", type="string", action="store", dest="loglevel", help="Loglevel")

        (self.options,self.args) = parser.parse_args()

        self.config = sams.core.Config(self.options.config,{})

        # Logging
        loglevel = self.options.loglevel
        if not loglevel:
            loglevel = self.config.get([id,'loglevel'],'ERROR')
        if not loglevel:
            loglevel = self.config.get(['common','loglevel'],'ERROR')
        loglevel_n = getattr(logging, loglevel.upper(), None)
        if not isinstance(loglevel_n, int):
            raise ValueError('Invalid log level: %s' % loglevel)
        logfile = self.options.logfile
        if not logfile:
            logfile = self.config.get([id,'logfile'])
        if not logfile:
            logfile = self.config.get(['common','logfile'])
        logformat = self.config.get([id,'logformat'],'%(asctime)s %(name)s:%(levelname)s %(message)s')
        if logfile:
            logging.basicConfig(filename=logfile, filemode='a',
                                format=logformat,level=loglevel_n)
        else:
            logging.basicConfig(format=logformat,level=loglevel_n) 

    def start(self):
        self.loaders = []
        self.aggregators = []

        for l in self.config.get([id,'loaders'],[]):
            try:
                Loader = sams.core.ClassLoader.load(l,'Loader')
                loader = Loader(l,self.config)
                self.loaders.append(loader)
            except Exception as e:
                logger.error("Failed to initialize: %s" % l)
                logger.error(e)
                exit(1)

        for a in self.config.get([id,'aggregators'],[]):
            try:
                Aggregator = sams.core.ClassLoader.load(a,'Aggregator')
                aggregator = Aggregator(a,self.config)
                self.aggregators.append(aggregator)
            except Exception as e:
                logger.error("Failed to initialize: %s" % a)
                logger.error(e)
                exit(1)

        logger.debug("Start loading %s",self.loaders)
        for l in self.loaders:
            l.load()
            while True:
                data = l.next()
                if not data:
                    break
                try:
                    logger.debug("Data: %s",data)
                    for a in self.aggregators:
                        a.aggregate(data)
                    l.commit()
                except Exception as e:
                    logger.error("Failed to do aggregation")
                    logger.exception(e)

                    # Cleanup of the aggregators.
                    for a in self.aggregators:
                        a.cleanup()
                    l.error()

        # Close down the aggregagors.
        for a in self.aggregators:
            a.close()


if __name__ == "__main__":
    Main().start()
