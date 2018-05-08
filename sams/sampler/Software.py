
import sams.base
import time
import os
import re

import logging
logger = logging.getLogger(__name__)

class Process():
    def __init__(self,pid,jobid):
        self.pid = pid
        self.tasks = {}
        self.clock_tics = os.sysconf(os.sysconf_names['SC_CLK_TCK'])
        self.starttime = time.time()
        self.ignore = False

        try:
            self.exe = os.readlink('/proc/%d/exe' % self.pid)
        except IOError as err:
            logger.debug("Pid: %d (JobId: %d) has no exe or pid has disapeard",pid,jobid)
            self.ignore = True
            return

    def _parse_stat(self,stat):
        """ Parse the relevant content from /proc/***/stat """

        m = re.search(r'^\d+ \(.*\) [RSDZTyEXxKWP] (.*)',stat)
        stats = m.group(1).split(r' ')
        return {
            'user'  : float(stats[14-4])/self.clock_tics,   # User CPU time in s.
            'system': float(stats[15-4])/self.clock_tics,   # System CPU time in s.
        }

    def update(self,uptime):
        """ Update information about pids """

        self.uptime = uptime

        try:
            tasks = filter(lambda f: re.match('^\d+$',f),os.listdir('/proc/%d/task' % self.pid))
            tasks = map(lambda t: int(t),tasks)
        except IOError as err:
            # Ignore if no tasks exists anymore (missing pid)
            logger.debug("No pids left/or no pids yet, should not happen")
            return
        
        for task in tasks:
            try:
                with open('/proc/%d/task/%d/stat' % (self.pid,task)) as f:
                    stat = f.read()
                    stats = self._parse_stat(stat)               
                    self.tasks[task] = { 
                            'user': stats['user'],
                            'system': stats['system'],
                        }
                    
            except IOError as err:
                logger.debug("Ignore missing task for pid: %d", self.pid)
                # Ignore missing task (or pid)
                pass

        self.updated = time.time()      

    def aggregate(self):
        """ Return the aggregated information for all tasks """
        return {
            'starttime': self.starttime,
            'exe': self.exe,
            'user': sum(t['user'] for t in self.tasks.values()),
            'system': sum(t['system'] for t in self.tasks.values()),
        }

class Sampler(sams.base.Sampler):
    def __init__(self,id,outQueue,config):
        super().__init__(id,outQueue,config)
        self.processes = {}
        self.create_time = time.time()

    def sample(self):
        logger.debug("sample()")

        with open('/proc/uptime', 'r') as f:
            uptime = float(f.readline().split()[0])
        
        for pid in self.pids:
            if not pid in self.processes.keys():
                self.processes[pid] = Process(pid,self.jobid)
            self.processes[pid].update(uptime)

    def last_updated(self):
        procs = list(filter(lambda p: not p.ignore,self.processes.values()))
        if not len(procs):
            return self.create_time
        return int(max(p.updated for p in procs))

    def start_time(self):
        procs = list(filter(lambda p: not p.ignore,self.processes.values()))
        if not len(procs):
            return 0
        return int(min(p.starttime for p in procs))

    def final_data(self):
        logger.debug("%s final_data" % self.id)
        aggr = {}
        total = { 'user': 0.0, 'system': 0.0 }
        for a in [p.aggregate() for p in filter(lambda p: not p.ignore, self.processes.values())]:
            exe = a['exe']
            if not exe in aggr:
                aggr[exe] = { 'user': 0.0, 'system': 0.0 }
            aggr[exe]['user'] += a['user']
            aggr[exe]['system'] += a['system']
            total['user'] += a['user']
            total['system'] += a['system']

        return { 
            'execs': aggr,
            'start_time': self.start_time(),
            'end_time': self.last_updated(),
        }
