/**
 * echarts图表函数库
 * 包含灵活的图表配置函数和各种专用图表函数
 */

/**
 * 创建一个完全灵活可配置的图表
 * @param {string} chartid - 图表容器的DOM ID
 * @param {string} title - 图表标题
 * @param {Array} xData - X轴数据数组
 * @param {Array} seriesConfig - 数据系列配置数组，每个元素包含:
 *                              - name: 系列名称
 *                              - type: 图表类型(line/bar等)
 *                              - data: 数据数组
 *                              - yAxisIndex: Y轴索引
 *                              - 其他样式配置
 * @param {Object} options - 可选的图表配置项
 */
function echarts_flexible(chartid, title, xData, seriesConfig, options = {}) {
    // 初始化图表实例
    let myChart = echarts.init(document.getElementById(chartid));
    
    // 默认的颜色方案
    const defaultColors = [
        '#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de',
        '#3ba272', '#fc8452', '#9a60b4', '#ea7ccc', '#6e7079'
    ];

    // 从系列配置中提取图例数据
    const legends = seriesConfig.map(item => item.name);
    
    // 处理每个数据系列的配置
    let series = seriesConfig.map((item, index) => {
        // 构建基础系列配置
        const seriesItem = {
            name: item.name,
            type: item.type || 'line',  // 默认为折线图
            data: item.data,
            yAxisIndex: item.yAxisIndex || 0,  // 默认使用第一个Y轴
            stack: item.stack,  // 堆叠配置
            // 线条相关配置
            smooth: item.smooth || false,  // 是否平滑曲线
            symbol: item.symbol || 'emptyCircle',  // 数据点样式
            symbolSize: item.symbolSize || 4,  // 数据点大小
            areaStyle: item.areaStyle,  // 区域填充样式
            // 柱状图相关配置
            barWidth: item.barWidth || '60%',  // 柱子宽度
            barGap: item.barGap || '0%',  // 柱间距
            // 样式配置
            lineStyle: {
                color: item.color || defaultColors[index % defaultColors.length],
                width: item.lineWidth || 2,
                type: item.lineType || 'solid'  // 线条类型：实线、虚线、点线
            },
            itemStyle: {
                color: item.color || defaultColors[index % defaultColors.length]
            }
        };
        
        return seriesItem;
    });
    
    // Y轴配置处理
    let yAxis = [];
    
    // 处理自定义Y轴配置
    if (options.yAxis) {
        if (Array.isArray(options.yAxis)) {
            yAxis = options.yAxis;
        } else {
            yAxis = [options.yAxis];
        }
    } else {
        // 创建默认Y轴配置
        yAxis = [{
            type: 'value',
            name: options.yAxisName || '',
            min: options.yAxisMin,
            max: options.yAxisMax,
            axisLabel: {
                formatter: options.yAxisFormatter || '{value}'
            }
        }];
        
        // 根据需要添加额外的Y轴
        const maxYAxisIndex = Math.max(...seriesConfig.map(item => item.yAxisIndex || 0));
        for (let i = 1; i <= maxYAxisIndex; i++) {
            yAxis.push({
                type: 'value',
                name: options[`yAxisName${i+1}`] || '',
                min: options[`yAxisMin${i+1}`],
                max: options[`yAxisMax${i+1}`],
                axisLabel: {
                    formatter: options[`yAxisFormatter${i+1}`] || '{value}'
                },
                position: i % 2 === 1 ? 'right' : 'left'  // 交替放置在左右两侧
            });
        }
    }
    
    // 构建完整的图表配置
    let option = {
        // 标题配置
        title: {
            text: title,
            x: options.titlePosition || 'center',
            textStyle: {
                color: options.titleColor || '#333',
                fontSize: options.titleSize || 20
            }
        },
        // 提示框配置
        tooltip: {
            trigger: 'axis',
            axisPointer: {
                type: options.axisPointerType || 'shadow'
            }
        },
        // 图例配置
        legend: {
            data: legends,
            bottom: options.legendBottom || 0
        },
        // 图表网格配置
        grid: {
            left: options.gridLeft || '3%',
            right: options.gridRight || '4%',
            bottom: options.gridBottom || '10%',
            containLabel: true
        },
        // 工具箱配置
        toolbox: {
            feature: {
                saveAsImage: {},  // 保存图片
                dataZoom: {},     // 数据缩放
                dataView: { readOnly: false },  // 数据视图
                restore: {},      // 重置
                magicType: {     // 动态类型切换
                    type: ['line', 'bar', 'stack']
                }
            }
        },
        // X轴配置
        xAxis: {
            type: 'category',
            boundaryGap: options.boundaryGap !== undefined ? options.boundaryGap : true,
            data: xData,
            name: options.xAxisName || ''
        },
        yAxis: yAxis,
        series: series
    };
    
    // 设置图表配置并返回图表实例
    myChart.setOption(option);
    return myChart;
}

/**
 * 创建单层饼图
 * @param {string} chartid - 图表容器的DOM ID
 * @param {string} title - 图表标题
 * @param {Array} data - 饼图数据数组，每个元素包含name和value
 * @param {Object} options - 可选的图表配置项
 */
function echarts_simple_pie(chartid, title, data, options = {}) {
    // 初始化图表实例
    let myChart = echarts.init(document.getElementById(chartid));
    
    // 默认颜色方案
    const defaultColors = [
        '#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de',
        '#3ba272', '#fc8452', '#9a60b4', '#ea7ccc', '#6e7079'
    ];

    // 构建饼图配置
    let option = {
        // 标题配置
        title: {
            text: title,
            x: options.titlePosition || 'center',
            textStyle: {
                color: options.titleColor || '#333',
                fontSize: options.titleSize || 20
            }
        },
        // 提示框配置
        tooltip: {
            trigger: 'item',
            formatter: options.tooltipFormatter || '{a} <br/>{b}: {c} ({d}%)'
        },
        // 图例配置
        legend: {
            orient: options.legendOrient || 'vertical',
            left: options.legendLeft || 'right',
            bottom: options.legendBottom || 0
        },
        // 系列配置
        series: [
            {
                name: title,
                type: 'pie',
                radius: options.radius || ['0%', '65%'],
                center: options.center || ['50%', '50%'],
                // 数据处理，添加颜色配置
                data: data.map(function(item, index) {
                    return Object.assign({}, item, {
                        itemStyle: {
                            color: defaultColors[index % defaultColors.length]
                        }
                    });
                }),
                // 标签配置
                label: {
                    formatter: options.labelFormatter || '{b}\n{d}%',
                    position: options.labelPosition || 'outside'
                },
                // 标签引导线配置
                labelLine: {
                    length: options.labelLineLength || 40,
                    length2: options.labelLineLength2 || 20
                },
                // 高亮效果配置
                emphasis: {
                    itemStyle: {
                        shadowBlur: 10,
                        shadowOffsetX: 0,
                        shadowColor: 'rgba(0, 0, 0, 0.5)'
                    }
                }
            }
        ]
    };

    // 添加工具箱配置（可选）
    if (options.showToolbox !== false) {
        option.toolbox = Object.assign({
            feature: {
                saveAsImage: {},  // 保存图片
                restore: {},      // 重置
                dataView: { readOnly: false }  // 数据视图
            }
        }, options.toolbox || {});
    }
    
    // 设置图表配置并返回图表实例
    myChart.setOption(option);
    return myChart;
}

/**
 * 创建嵌套饼图（双层饼图）
 * @param {string} chartid - 图表容器的DOM ID
 * @param {string} title - 图表标题
 * @param {Array} innerData - 内层饼图数据
 * @param {Array} outerData - 外层饼图数据
 * @param {Object} options - 可选的图表配置项
 */
function echarts_nested_pie(chartid, title, innerData, outerData, options = {}) {
    // 初始化图表实例
    let myChart = echarts.init(document.getElementById(chartid));
    
    // 默认颜色方案
    const defaultColors = [
        '#5470c6', '#91cc75', '#fac858', '#ee6666', '#73c0de',
        '#3ba272', '#fc8452', '#9a60b4', '#ea7ccc', '#6e7079'
    ];
    
    // 合并内外层的图例数据
    const legendData = innerData.map(function(item) {
        return item.name;
    }).concat(outerData.map(function(item) {
        return item.name;
    }));
    
    // 构建嵌套饼图配置
    let option = {
        // 标题配置
        title: {
            text: title,
            x: options.titlePosition || 'center',
            textStyle: {
                color: options.titleColor || '#333',
                fontSize: options.titleSize || 20
            }
        },
        // 提示框配置
        tooltip: {
            trigger: 'item',
            formatter: options.tooltipFormatter || '{a} <br/>{b}: {c} ({d}%)'
        },
        // 图例配置
        legend: {
            data: legendData,
            bottom: options.legendBottom || 0,
            orient: options.legendOrient || 'horizontal',
            left: options.legendLeft || 'center'
        },
        // 系列配置（包含内外两层饼图）
        series: [
            // 内层饼图配置
            {
                name: options.innerName || '内层',
                type: 'pie',
                selectedMode: options.selectedMode || 'single',
                radius: options.innerRadius || [0, '30%'],
                // 数据处理，添加颜色配置
                data: innerData.map(function(item, index) {
                    return Object.assign({}, item, {
                        itemStyle: {
                            color: defaultColors[index % defaultColors.length]
                        }
                    });
                }),
                // 标签配置
                label: {
                    position: options.innerLabelPosition || 'inner',
                    fontSize: options.innerLabelSize || 14,
                    formatter: options.innerLabelFormatter || '{b}\n{d}%',
                    show: options.showInnerLabel !== false
                },
                labelLine: {
                    show: options.showInnerLabelLine !== false
                }
            },
            // 外层饼图配置
            {
                name: options.outerName || '外层',
                type: 'pie',
                radius: options.outerRadius || ['45%', '60%'],
                // 数据处理，添加颜色配置
                data: outerData.map(function(item, index) {
                    return Object.assign({}, item, {
                        itemStyle: {
                            color: defaultColors[(index + innerData.length) % defaultColors.length]
                        }
                    });
                }),
                // 标签配置
                label: {
                    formatter: options.outerLabelFormatter || '{b}: {c} ({d}%)',
                    position: options.labelPosition || 'outside'
                },
                // 标签引导线配置
                labelLine: {
                    length: options.labelLineLength || 30,
                    length2: options.labelLineLength2 || 20
                }
            }
        ]
    };

    // 添加工具箱配置（可选）
    if (options.showToolbox !== false) {
        option.toolbox = Object.assign({
            feature: {
                saveAsImage: {},  // 保存图片
                restore: {},      // 重置
                dataView: { readOnly: false }  // 数据视图
            }
        }, options.toolbox || {});
    }
    
    // 设置图表配置并返回图表实例
    myChart.setOption(option);
    return myChart;
}

/**
 * 通过AJAX加载并渲染嵌套饼图
 * @param {string} url - 数据接口URL
 * @param {string} chartid - 图表容器的DOM ID
 */
function ajax_render_nested_pie(url, chartid) {
    return $.getJSON(url, function(data) {
        echarts_nested_pie(
            chartid,
            data.title,
            data.innerData,
            data.outerData,
            data.options || {}
        );
    });
}

/**
 * 通过AJAX加载并渲染单层饼图
 * @param {string} url - 数据接口URL
 * @param {string} chartid - 图表容器的DOM ID
 */
function ajax_render_simple_pie(url, chartid) {
    return $.getJSON(url, function(data) {
        echarts_simple_pie(
            chartid,
            data.title,
            data.data,
            data.options || {}
        );
    });
}