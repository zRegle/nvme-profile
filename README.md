根据这篇[paper](https://dl.acm.org/doi/pdf/10.1145/3093337.3037732)来对nvme设备进行profile的工具

### 说明

```
profile.py        =====> 运行spdk fio_plugin对nvme设备进行性能测试，收集数据
devmodel.py       =====> 根据测试数据对设备建模, 得出<IOPS, tail latency>曲线和write factor
compute_token.py  =====> 根据设备模型，给定latency SLO，算出满足要求的令牌数
```
每个python文件都可以用`-h`选项查看用法

### 准备工作

1. 安装依赖的库：

   ```shell
   yum -y install python3
   yum -y install python3-pip
   pip3 install numpy
   pip3 install matplotlib
   pip3 install scikit-learn
   ```

2. 编译fio

   下载fio源码，建议至少切换到3.3及以上版本

   ```shell
   git clone https://github.com/axboe/fio
   cd fio
   git checkout fio-3.18
   make -j12
   ```

3. 编译spdk

   下载spdk源码，然后运行SPDK configure脚本以启用fio（将其指向fio代码库的根）

   ```shell
   git clone https://github.com/spdk/spdk
   cd spdk
   git submodule update --init
   ./configure--with-fio=/path/to/fio/repo <other configuration options>
   make -j all
   ```

### 测试nvme设备

1. 运行spdk的setup.sh脚本，接管nvme设备：

   ```shell
   cd spdk
   HUGEMEM=4096 ./scripts/setup.sh
   0000:02:00.0 (8086 0953): nvme -> uio_pci_generic
   ```

2. 运行profile.py，进行测试（140轮的fio测试，每轮默认2分钟）：

   ```shell
   python3 ./profile_dev.py -o ./output -p 0000:02:00.0 -s /home/spdk -f /home/fio
   ```

### 设备建模

1. 测试完成后，在输出目录下会有以下fio测试数据：

   ```
   read-50%.json
   read-75%.json
   read-90%.json
   read-95%.json
   read-99%.json
   ```

   运行devmodel.py，对设备建模（默认选择p99.9延迟），等待建模完成输出write factor：

   ```shell
   python3 ./devmodel.py ./output
   Write factor is: 4.4
   ```

   建模完成后，对应尾延迟的输出目录下会有：

   ```
   performance.svg ===> 设备性能曲线图
   devmodel.bin  ===> 设备模型
   ```

2. 运行compute_token.py，给定latency SLO，算出令牌数量：

   ```
   python3 ./compute_token.py ./output/99.9/devmodel.bin 3000
   546830
   ```

   
