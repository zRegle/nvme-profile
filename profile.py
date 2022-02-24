import json
import os
import argparse
import subprocess


def parse_json(path):
    _file = open(path, "rb")
    _json = json.load(_file)
    data = _json["jobs"]

    job = data[0]

    job_result = {}
    read_stat = job["read"]
    job_result["r_iops"] = round(read_stat["iops"]/1000, 3)
    job_result["r_clat"] = read_stat["clat_ns"]["percentile"]

    write_stat = job["write"]
    job_result["w_iops"] = round(write_stat["iops"]/1000, 3)

    return job_result


def serialize_res(path, d):
    f = open(path, "w")
    dict_str = json.dumps(d)
    f.write(dict_str)
    f.close()

def get_max_iops():
    # run 100% read test to get device max iops
    cmd = "{} -direct=1 -iodepth 64 -thread -rw=randread " \
          "-ioengine={} -bs=4K -numjobs={} -runtime={} " \
          "-group_reporting -norandommap -name=rand_rw " \
          "'--filename=trtype=PCIe traddr={} ns=1' " \
          "--output=raw --output-format=json+". \
        format(fio_dir, spdk_engine, num_jobs, run_time, pci_addr)
    subprocess.call(cmd, shell=True)
    res = parse_json(root_dir + "/raw")
    return res["r_iops"]


def run_fio():
    for r in read_ratio:
        iops_lat_dict = {}
        job_name = "read-{}%".format(r)
        cur_iops = 50 * unit
        while cur_iops <= max_iops:
            r_iops_per_thread = int(cur_iops * float(r) / 100 / num_jobs)
            w_iops_per_thread = int(cur_iops * (1 - float(r) / 100) / num_jobs)
            cmd = "{} -direct=1 -iodepth 64 -thread -rw=randrw -rwmixread={} " \
                  "-ioengine={} -bs=4K -numjobs={} -runtime={} -rate_iops={},{} " \
                  "-group_reporting -norandommap -name=rand_rw " \
                  "'--filename=trtype=PCIe traddr={} ns=1' " \
                  "--output=raw --output-format=json+". \
                format(fio_dir, r, spdk_engine, num_jobs, run_time,
                       r_iops_per_thread, w_iops_per_thread, pci_addr)
            subprocess.call(cmd, shell=True)
            res = parse_json(root_dir + "/raw")
            iops_lat_dict[(res["r_iops"], res["w_iops"])] = res["r_clat"]
            cur_iops += 10 * unit
        od = sorted(iops_lat_dict.items(), key=lambda x: sum(x[0]))
        # serialize result
        path = "{}/{}.json".format(output, job_name)
        serialize_res(path, od)


parser = argparse.ArgumentParser("Run fio to collect data")
parser.add_argument('-o', '--output', help="the directory where data is placed", required=False)
parser.add_argument('-p', '--pci_address', help="nvme device pci address", required=True)
parser.add_argument('-s', '--spdk_path', help="path to spdk repo", required=True)
parser.add_argument('-f', '--fio_path', help="path to fio repo", required=True)
parser.add_argument('-t', '--run_time', default=120, help="each fio test runtime", type=int, required=False)
parser.add_argument('-n', '--num_jobs', default=4, help="fio num_jobs", type=int, required=False)
args = parser.parse_args()

# fio parameters
read_ratio = [50, 75, 90, 95, 99]

root_dir = os.getcwd()
output = args.output if args.output else root_dir
spdk_engine = "{}/build/fio/spdk_nvme".format(args.spdk_path)
fio_dir = "{}/fio".format(args.fio_path)
pci_addr = args.pci_address.replace(':', '.')
run_time = args.run_time
num_jobs = args.num_jobs

max_iops = get_max_iops()
unit = 1000

run_fio()
