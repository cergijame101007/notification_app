let chartInstance = null;
async function getAndPlotData() {
    const start = performance.now();
    try {
        const response = await fetch("/temperature/");
        if (!response.ok) throw new Error(`温度データ取得失敗: ${response.status}`);
        const temperatureData = await response.json();

        const accumResponse = await fetch("/accumulative_temperature/");
        if (!accumResponse.ok) throw new Error(`積算温度取得失敗: ${accumResponse.status}`);
        const accumulateData = await accumResponse.json();

        const timestamps = temperatureData.map(entry => entry.timestamp);
        const temperatures = temperatureData.map(entry => entry.temperature);
        const accumulateTemperature = accumulateData.accumulative_temperature.toFixed(2);

        const maxPoints = accumulateData.max_points || []

        const redPointData = timestamps.map(ts => {
            const match = maxPoints.find(p => {
                const d1 = new Date(ts);
                const d2 = new Date(p[0].replace(" ", "T"));
                return d1.getTime() === d2.getTime();
            });
            return match ? match[1] : null;
        });


        console.log("一致している赤点数:", redPointData.filter(v => v !== null).length);

        document.getElementById("accum-text").textContent = `積算温度：${accumulateTemperature} ℃`;

        const ctx = document.getElementById('temperatureChart').getContext('2d');

        if (chartInstance) {
            chartInstance.destroy();
        }

        chartInstance = new Chart(ctx, {
            type: 'line',
            data: {
                labels: timestamps,
                datasets: [
                    {
                        label: '温度 [℃]',
                        data: temperatures,
                        borderColor: 'blue',
                        backgroundColor: 'rgba(0, 0, 255, 0.1)',
                        tension: 0.3,
                        fill: true,
                        pointRadius: 0
                    },
                    {
                        label: '積算対象点 (最大点)',
                        data: redPointData,
                        borderColor: 'red',
                        backgroundColor: 'red',
                        pointRadius: 3,
                        pointStyle: 'circle',
                        borderWidth: 0,
                        showLine: false
                    }
                ]
            },
            options: {
                responsive: true,
                plugins: {
                    title: {
                        display: true,
                        text: '温度と積算温度'
                    },
                    legend: {
                        display: true
                    }
                },
                scales: {
                    x: {
                        title: {
                            display: true,
                            text: '時刻'
                        },
                        ticks: {
                            maxRotation: 60,
                            minRotation: 45,
                            autoSkip: true,
                            maxTicksLimit: 30
                        }
                    },
                    y: {
                        suggestedMin: 10.0,
                        suggestedMax: 30.0,
                        ticks: {
                            stepSize: 0.1
                        },
                        title: {
                            display: true,
                            text: '温度 [℃]'
                        }
                    }
                }
            }
        });
        const end = performance.now();
        console.log(`⏱️ グラフ描画完了までの時間: ${(end - start).toFixed(2)}ms`);
    } catch (error) {
        console.error("エラー:", error.message);
        document.getElementById("accum-text").textContent = "積算温度：取得失敗";
    }
}

document.addEventListener("DOMContentLoaded", getAndPlotData);
