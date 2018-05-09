
import sams.base
import os
import re

import logging
logger = logging.getLogger(__name__)

class Sampler(sams.base.Sampler):
    processes = {}

    cgroup_base = '/sys/fs/cgroup'
    cgroup = None

    def sample(self):
        if self._get_cgroup():
            return

        logger.debug("sample()")

        cpus = self._cpucount(self.read_cgroup('cpuset','cpuset.cpus'))
        memory_usage = self.read_cgroup('memory','memory.usage_in_bytes')
        memory_limit = self.read_cgroup('memory','memory.limit_in_bytes')
        memory_max_usage = self.read_cgroup('memory','memory.max_usage_in_bytes')

        self.store({
                'cpus' : cpus,
                'memory_usage': memory_usage,
                'memory_limit': memory_limit,
                'memory_max_usage': memory_max_usage,
            })

    def _get_cgroup(self):
        """ Get the cgroup base path for the slurm job """
        if self.cgroup:
            return False
        try:
            with open("/proc/%d/cpuset" % self.pids[0],"r") as file:
                cpuset = file.readline()
                m = re.search(r'^/(slurm/uid_\d+/job_\d+)/',cpuset)
                if m:
                    self.cgroup = m.group(1)
                    return False
        except IOError as e:
            logger.debug("Failed to fetch cpuset for pid: %d", self.pids[0])
            return True

    def _cpucount(self,count):
        """ Calculate number of cpus from a "N,N-N"-structure """
        cpu_count = 0
        for c in count.split(","):
            m = re.search(r'^(\d+)-(\d+)$',c)
            if m:
                cpu_count += int(m.group(2))-int(m.group(1))+1
            m = re.search(r'^(\d+)$',c)
            if m:
                cpu_count += 1
        return cpu_count

    
    def read_cgroup(self,type,id):
        try:
            with open(os.path.join(self.cgroup_base,type,self.cgroup,id),"r") as file:
                return file.readline().strip()
        except IOError as err:
            logger.debug("Failed to open %s for reading",os.path.join(self.cgroup_base,type,self.cgroup,id))
            return ""

    def final_data(self):
        return {}