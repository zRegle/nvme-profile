import numpy as np
import math
import pickle
import argparse


def compute_tokens(devmodel, latSLO):
    job_result = devmodel["job_result"]
    iops_list = []
    for name, result in job_result.items():
        if max(result["lat"]) <= latSLO:
            iops_list.append(max(result["weighted_iops"]))
            continue
        p = result["function"]
        coef = p.coef
        coef[-1] = coef[-1] - latSLO
        roots = np.roots(p)
        """
        remove complex root
        1.First, get root whose image is zero, that is, the real root
        2.Second, after step 1, the root is still in complex form, transform into float 
        """
        real_root_complex = list(filter(lambda r: np.imag(r) == 0, roots))
        real_root_float = list(map(lambda c: np.real(c), real_root_complex))
        # get iops fall in reasonable range
        upper_bound = max(result["weighted_iops"])
        lower_bound = min(result["weighted_iops"])
        reasonable_root = list(filter(lambda x: lower_bound <= x <= upper_bound, real_root_float))
        if reasonable_root:
            # get the maximum iops
            iops_list.append(max(reasonable_root))
    return math.floor(np.mean(iops_list) * 1000)


if __name__ == "__main__":
    parser = argparse.ArgumentParser("Compute tokens")
    parser.add_argument("dev_model", help="binary file that stores device model")
    parser.add_argument("latency", type=float, help="tail latency requirement")
    args = parser.parse_args()

    with open(args.dev_model, "rb") as f:
        devmodel = pickle.load(f)
        f.close()
    print(compute_tokens(devmodel, args.latency))
