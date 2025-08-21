function formatNumber (n) {
            n = n.toString()
            return n[1] ? n : '0' + n;
        }
        function formatTime (number, format) {
            let time = new Date(number)
            let newArr = []
            let formatArr = ['Y', 'M', 'D', 'h', 'm', 's']
            newArr.push(time.getFullYear())
            newArr.push(formatNumber(time.getMonth() + 1))
            newArr.push(formatNumber(time.getDate()))

            newArr.push(formatNumber(time.getHours()))
            newArr.push(formatNumber(time.getMinutes()))
            newArr.push(formatNumber(time.getSeconds()))

            for (let i in newArr) {
                format = format.replace(formatArr[i], newArr[i])
            }
            return format;
        }


function echart_final_line_if_speed(chartid, labelname, lengends, datas, starttime) {
    let chart = echarts.init(document.getElementById(chartid)); // 找到HTML中id为chartid的标签

    let option = {
        title: {
            text: labelname
        },
        tooltip: {
            formatter: function (params) {
                let res = '<div>时间：' + formatTime((params[0].data)[0], 'Y-M-D h:m:s') + '</div>';

                params.forEach(function (item) {
                    res += '<i class="fa fa-circle" style="color:' + item.color + '"></i> '
                        + item.seriesName.replace(/Av.*/, '')
                        + ': ' + formatSpeed(item.data[1]) + '<br/>';
                });

                return res;
            },
            trigger: 'axis',
            axisPointer: {
                type: 'cross'
            }
        },
        legend: {
            left: '5%',
            bottom: '10%',
            data: lengends
        },
        grid: {
            left: 'left',
            bottom: 130, // 增加 grid 底部距离，避免 legend 与 dataZoom 重叠
            y2: 100,
            containLabel: true
        },
        toolbox: {
            right: '10%',
            feature: {
                saveAsImage: {} // 保存图片功能
            }
        },
        xAxis: {
            splitNumber: 16,
            type: 'time',
            boundaryGap: false,
        },
        dataZoom: [{
            startValue: starttime
        }, {
            type: 'inside'
        }],
        yAxis: {
            type: 'value',
            axisLabel: {
                formatter: function (value) {
                    return formatSpeed(value);
                }
            }
        },
        series: datas.map(function (series) {
            return {
                ...series,
                markPoint: {
                    data: [
                        {
                            type: 'max',
                            name: '最大值',
                            label: {
                                formatter: function (param) {
                                    return formatSpeed(param.value);
                                }
                            }
                        },
                        {
                            type: 'min',
                            name: '最小值',
                            label: {
                                formatter: function (param) {
                                    return formatSpeed(param.value);
                                }
                            }
                        }
                    ]
                }
            };
        })
    };

    chart.setOption(option);
}

function formatSpeed(value) {
    if (value >= 1e9) {
        return (value / 1e9).toFixed(2) + ' Gbps';
    } else if (value >= 1e6) {
        return (value / 1e6).toFixed(2) + ' Mbps';
    } else if (value >= 1e3) {
        return (value / 1e3).toFixed(2) + ' kbps';
    } else {
        return value + ' bps';
    }
}


function echart_final_line_cpu_usage(chartid, labelname, legends, datas, starttime) {
    // 销毁旧实例，防止内存泄漏
    if (echarts.getInstanceByDom(document.getElementById(chartid))) {
        echarts.dispose(document.getElementById(chartid));
    }
    let chart = echarts.init(document.getElementById(chartid));

    let option = {
        title: {
            text: labelname
        },
        tooltip: {
            trigger: 'axis',
            axisPointer: {
                type: 'shadow'
            },
            formatter: function (params) {
                let res = '<div>时间：' + formatTime((params[0].data)[0], 'Y-M-D h:m:s') + '</div>';
                params.forEach(function (item) {
                    res += '<i class="fa fa-circle" style="color:' + item.color + '"></i> '
                        + item.seriesName.replace(/Av.*/, '')
                        + ': ' + item.data[1] + ' %' + '<br/>';
                });
                return res;
            }
        },
        legend: {
            left: '5%',
            bottom: '10%',
            data: legends
        },
        grid: {
            left: '5%',
            right: '5%',
            bottom: '18%',
            containLabel: true
        },
        toolbox: {
            right: '10%',
            feature: {
                saveAsImage: {},
                restore: {},
                dataView: { readOnly: false }
            }
        },
        xAxis: {
            splitNumber: 16,
            type: 'time',
            boundaryGap: false
        },
        dataZoom: [
            {
                type: 'slider',
                show: true,
                startValue: starttime
            },
            {
                type: 'inside'
            }
        ],
        yAxis: {
            type: 'value',
            axisLabel: {
                formatter: '{value} %'
            }
        },
        series: datas.map(series => ({
            ...series,
            emphasis: {
                focus: 'series'
            }
        })),
        // ECharts 5.4+ 响应式
        responsive: true
    };

    chart.setOption(option);
}


function get_json_render_echart_line_if_speed(url, chartid) {
            $.getJSON(url,function(data) {//请求URL的JSON,得到数据data,下面是对data的处理
                                            echart_final_line_if_speed(chartid, data.labelname, data.lengends, data.datas, data.starttime)
                                          });
            }

function get_json_render_echart_line_cpu_usage(url, chartid) {
    $.getJSON(url)
        .done(function (data) {
            // 兼容后端数据结构
            echart_final_line_cpu_usage(
                chartid,
                data.labelname,
                data.legends, // 注意这里用data.legends
                data.datas,
                data.starttime
            );
        })
        .fail(function () {
            // 错误处理
            let dom = document.getElementById(chartid);
            if (dom) dom.innerHTML = '<div style="color:red;text-align:center;">数据加载失败</div>';
        });
}