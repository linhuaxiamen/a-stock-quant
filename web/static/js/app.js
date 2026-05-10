/* A股量化 Web 前端工具 */

// 通用 AJAX GET
function apiGet(url, callback) {
    fetch(url)
        .then(function(r) { return r.json(); })
        .then(callback)
        .catch(function(err) { console.error('API Error:', url, err); });
}

// 轮询直到条件满足
function pollUntil(url, interval, isDone, onDone, onProgress) {
    function tick() {
        apiGet(url, function(data) {
            if (onProgress) onProgress(data);
            if (isDone(data)) { onDone(data); return; }
            setTimeout(tick, interval);
        });
    }
    tick();
}

// ECharts 净值曲线
function renderEquityChart(containerId, equityData) {
    var chart = echarts.init(document.getElementById(containerId));
    chart.setOption({
        tooltip: {
            trigger: 'axis',
            axisPointer: { type: 'cross' }
        },
        legend: {
            data: ['策略净值', '买入持有'],
            top: 5
        },
        grid: {
            left: 60, right: 20, top: 40, bottom: 50
        },
        xAxis: {
            type: 'category',
            data: equityData.dates,
            axisLabel: {
                formatter: function(v) { return v.substring(0, 7); }
            }
        },
        yAxis: {
            type: 'value',
            scale: true,
            name: '市值(百万)',
            axisLabel: {
                formatter: function(v) { return v.toFixed(1); }
            }
        },
        dataZoom: [
            { type: 'inside', start: 0, end: 100 },
            { type: 'slider', start: 0, end: 100 }
        ],
        series: [
            {
                name: '策略净值',
                type: 'line',
                data: equityData.portfolio,
                smooth: true,
                lineStyle: { width: 2 },
                itemStyle: { color: '#5470c6' },
                areaStyle: {
                    color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                        { offset: 0, color: 'rgba(84,112,198,0.2)' },
                        { offset: 1, color: 'rgba(84,112,198,0.02)' }
                    ])
                }
            },
            {
                name: '买入持有',
                type: 'line',
                data: equityData.benchmark,
                lineStyle: { type: 'dashed', width: 1.5 },
                itemStyle: { color: '#91cc75' }
            }
        ]
    });

    // 响应式
    window.addEventListener('resize', function() { chart.resize(); });
    return chart;
}
