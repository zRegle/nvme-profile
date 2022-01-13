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


def run_fio():
    for r in read_ratio:
        iops_lat_dict = {}
        job_name = "read-{}%".format(r)
        for d in iodepth:
            for n in numjobs:
                cmd = "{} -direct=1 -iodepth {} -thread -rw=randrw -rwmixread={} " \
                      "-ioengine={} -bs=4K -numjobs={} -runtime={} " \
                      "-group_reporting -norandommap -name=rand_rw " \
                      "'--filename=trtype=PCIe traddr={} ns=1' " \
                      "--output=raw --output-format=json+". \
                    format(fio_dir, d, r, spdk_engine, n, run_time, pci_addr)
                subprocess.call(cmd, shell=True)
                res = parse_json(root_dir + "/raw")
                iops_lat_dict[(res["r_iops"], res["w_iops"])] = res["r_clat"]
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
args = parser.parse_args()

# fio parameters
read_ratio = [50, 75, 90, 95, 99]
iodepth = [1, 2, 4, 8, 16, 32, 64]
numjobs = [1, 2, 3, 4]

root_dir = os.getcwd()
output = args.output if args.output else root_dir
spdk_engine = "{}/build/fio/spdk_nvme".format(args.spdk_path)
fio_dir = "{}/fio".format(args.fio_path)
pci_addr = args.pci_address.replace(':', '.')
run_time = args.run_time

run_fio()
