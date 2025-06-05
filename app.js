async function getAndPlotData() {
    const dataUrl = "https://notification-app-0whl.onrender.com/temperature/";
    const accumUrl = "https://notification-app-0whl.onrender.com/accumulative_temperature/";
    try {
        const response = await fetch(dataUrl);
        if (!response.ok) throw new Error(`温度データ取得失敗: ${response.status}`);
        const temperatureJson = await response.json();

        const accumResponse = await fetch(accumUrl);
        if (!accumResponse.ok) throw new Error(`積算温度取得失敗: ${accumResponse.status}`);
        const accumData = await accumResponse.json();

        const timestamps = temperatureJson.map(entry => entry.timestamp);
        const temperatures = temperatureJson.map(entry => entry.temperature);
        const accumValue = accumData.accumulative_temperature.toFixed(2);

        document.getElementById("accum-text").textContent = `積算温度：${accumValue} ℃`;

        // グラフ描画
        const ctx = document.getElementById('tempChart').getContext('2d');
        new Chart(ctx, {
            type: 'line',
            data: {
                labels: timestamps,
                datasets: [{
                    label: '温度 [℃]',
                    data: temperatures,
                    borderColor: 'blue',
                    backgroundColor: 'rgba(0, 0, 255, 0.1)',
                    tension: 0.3,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    title: {
                        display: true,
                        text: '時間ごとの温度と積算温度'
                    },
                    legend: {
                        display: true
                    }
                },
                scales: {
                    x: {
                        ticks: {
                            maxRotation: 60,
                            minRotation: 45,
                            maxTicksLimit: 20
                        },
                        title: {
                            display: true,
                            text: '時刻'
                        }
                    },
                    y: {
                        title: {
                            display: true,
                            text: '温度 [℃]'
                        },
                        suggestedMin: 10,
                        suggestedMax: 40
                    }
                }
            }
        });

    } catch (error) {
        console.error("エラー:", error.message);
        document.getElementById("accum-text").textContent = "積算温度：取得失敗";
    }
}

window.onload = getAndPlotData;