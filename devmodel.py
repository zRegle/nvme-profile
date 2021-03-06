import os
import time
import argparse
import pickle
import json
import matplotlib.pyplot as plt
import numpy as np
from sklearn.covariance import EllipticEnvelope
from scipy import integrate
import matplotlib


# read data start
def deserialize_json(dir):
    iops_lat_dict = {}
    files = os.listdir(dir)
    for i in range(0, len(files)):
        path = os.path.join(dir, files[i])
        if os.path.isfile(path) and path.endswith('json'):
            f = open(path, "r")
            # [[r_iops, w_iops], r_clat_percentile]
            data = json.load(f)
            job_name = files[i].split('.')[0]
            iops_lat_dict[job_name] = data
            f.close()
    return iops_lat_dict


def process_raw(iops_lat_dict, dev_dir):
    tails = ["95.0", "99.0", "99.5", "99.9"]
    for p in tails:
        p_dir = "{}/{}".format(dev_dir, p)
        if not os.path.exists(p_dir):
            os.mkdir(p_dir)
        for name, stat in iops_lat_dict.items():
            # rw_iops
            iops = list(map(lambda stat: stat[0], stat))
            p_key = p + "00000"
            # latency percentile
            data = list(map(lambda stat: stat[1], stat))
            lat = np.array(list(map(lambda per: round(per[p_key]/1000, 3), data)))
            # transform into dict
            job_stat = []
            for i in range(0, len(iops)):
                job_stat.append([iops[i], lat[i]])
            # write file
            file_path = "{}/{}.json".format(p_dir, name)
            f = open(file_path, "w")
            dict_str = json.dumps(job_stat)
            f.write(dict_str)
            f.close()
# read data end


def curve_fit(raw_stat, factor):
    result = {}
    # curve_fitting
    rw_iops = list(map(lambda x: x[0], raw_stat))
    weighted_iops = [r + factor * w for r, w in rw_iops]
    lat = list(map(lambda x: x[1], raw_stat))
    coef = np.polyfit(weighted_iops, lat, poly_degree)
    f = np.poly1d(coef)
    result["weighted_iops"] = weighted_iops
    result["lat"] = lat
    result["f"] = f
    return result


def reduce_noise_gaussian(stat, factor):
    result = curve_fit(stat, factor)
    weighted_iops = result["weighted_iops"]
    lat = result["lat"]
    f = result["f"]
    # remove abnormal points with "3-sigma principle"
    gap = []
    # compute the diff between real lat and estimate data
    for j in range(len(weighted_iops)):
        diff = f(weighted_iops[j]) - lat[j]
        gap.append(diff)
    # apply "3-sigma principle"
    vec = np.array(gap).reshape(-1, 1)
    labels = EllipticEnvelope(random_state=0).fit_predict(vec)
    # remove data
    result["weighted_iops"] = []
    result["lat"] = []
    for j in range(len(labels)):
        if labels[j] == 1:
            result["weighted_iops"].append(weighted_iops[j])
            result["lat"].append(lat[j])
    return result


def calculate_area(f, g, left, right):
    f_area, _ = integrate.quad(f, left, right)
    g_area, _ = integrate.quad(g, left, right)
    return abs(f_area - g_area)


def build_devmodel(iops_lat_dict):
    cur = 1
    factor_upper_bound = 20
    step = 0.1
    devmodel = {}
    # measured by the area of the overlapped functions
    # lower score is better
    overlap_score = np.inf
    while cur <= factor_upper_bound:
        print("***********************START OF ITERATION-{:.1f}***********************".format(cur))
        iops_upper_bound = 0
        lat_upper_bound = 0
        job_result = {}
        ratios = []
        for name, raw_stat in iops_lat_dict.items():
            read_ratio = int(name.split('-')[1][:-1])
            ratios.append(read_ratio)
            cur_job = {}
            result = reduce_noise_gaussian(raw_stat, cur)
            weighted_iops = result["weighted_iops"]
            iops_upper_bound = max(iops_upper_bound, max(weighted_iops))
            lat = result["lat"]
            lat_upper_bound = max(lat_upper_bound, max(lat))
            coef = np.polyfit(weighted_iops, lat, poly_degree)
            f = np.poly1d(coef)
            cur_job["function"] = f
            cur_job["weighted_iops"] = weighted_iops
            cur_job["lat"] = lat
            job_result[read_ratio] = cur_job
        area = 0
        ratios.sort()
        for i in range(len(ratios)-1):
            now = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time()))
            print("{}: Processing ratio-{}".format(now, ratios[i]))
            res0 = job_result[ratios[i]]
            f = res0["function"]
            for j in range(i+1, len(ratios)):
                res1 = job_result[ratios[j]]
                g = res1["function"]
                # get the maximum of the minimum iops of job0 and job1
                iops_lower_bound = max(min(res0["weighted_iops"]), min(res1["weighted_iops"]))
                area += calculate_area(f, g, iops_lower_bound, iops_upper_bound)
        print("overlap score is {}".format(area))
        if overlap_score > area:
            overlap_score = area
            devmodel = {
                "factor": cur,
                "job_result": job_result,
            }
        print("***********************END OF ITERATION-{:.1f}***********************\n".format(cur))
        cur += step
    # save devmodel
    with open(dev_dir + "/devmodel.bin", "wb") as f:
        pickle.dump(devmodel, f)
    print("Write factor: {:.1f}".format(devmodel["factor"]))
    return devmodel


def load_model(dev_dir):
    with open(dev_dir + "/devmodel.bin", "rb") as f:
        devmodel = pickle.load(f)
    return devmodel


def plot_fig(dev_dir):
    devmodel = load_model(dev_dir)
    job_result = devmodel["job_result"]
    max_iops = max(map(lambda stat: max(stat["weighted_iops"]), job_result.values()))
    max_lat = max(map(lambda stat: max(stat["lat"]), job_result.values()))

    for read_ratio, result in job_result.items():
        c = color[read_ratio]
        l = "read-{}%".format(read_ratio)
        # plot
        min_iops = min(result["weighted_iops"])
        x = np.linspace(min_iops, max_iops, 100)
        # plt.scatter(result["weighted_iops"], result["lat"], color=c)
        plt.plot(x, result["function"](x), color=c, label=l,
                 marker=marker[read_ratio], markevery=5)

    plt.ylim(0, max_lat)
    plt.xlabel("Weighted IOPS(K)")
    plt.ylabel("p{} read latency(us)".format(p))
    plt.legend()
    plt.savefig("{}/performance.pdf".format(dev_dir), format="pdf")
    plt.show()


if __name__ == "__main__":
    color = {50: "blue", 75: "orange", 90: "green",
             95: "red", 99: "violet", 100: "cornflowerblue"}
    marker = {50: ".", 75: ",", 90: "o",
              95: "v", 99: "s", 100: "*"}
    font = {'size': 13}
    matplotlib.rc('font', **font)

    parser = argparse.ArgumentParser(description="Compute write cost factor")
    parser.add_argument("dev_dir", help="the dir stores device data")
    parser.add_argument('-p', '--percentage',
                        choices=[95.0, 99.0, 99.5, 99.9], default=99.9,
                        help="tail latency percentage",
                        type=float, required=False)
    parser.add_argument('-d', '--degree', default=4,
                        help="polynomial degree of the device model curve",
                        type=int, required=False)
    args = parser.parse_args()
    # args check
    poly_degree = args.degree
    if poly_degree <= 0:
        print('Polynomial degree must greater than zero: {}'.format(poly_degree))
        exit(-1)
    dev_dir = args.dev_dir
    p = args.percentage

    # process raw data
    iops_lat_dict = deserialize_json(dev_dir)
    process_raw(iops_lat_dict, dev_dir)
    # choose best write factor
    dev_dir = "{}/{}".format(dev_dir, p)
    iops_lat_dict = deserialize_json(dev_dir)
    build_devmodel(iops_lat_dict)
    plot_fig(dev_dir)
