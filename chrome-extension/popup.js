document.addEventListener('DOMContentLoaded', async () => {
    const startBtn = document.getElementById('startBtn');
    const stopBtn = document.getElementById('stopBtn');
    const exportBtn = document.getElementById('exportBtn');
    const statusText = document.getElementById('statusText');
    const stepCountDisplay = document.getElementById('stepCount');

    // Recupera o estado atual do background
    const response = await chrome.runtime.sendMessage({ action: "getState" });
    updateUI(response.isRecording, response.stepsCount);

    startBtn.addEventListener('click', async () => {
        const res = await chrome.runtime.sendMessage({ action: "startRecording" });
        updateUI(true, res.stepsCount);
    });

    stopBtn.addEventListener('click', async () => {
        const res = await chrome.runtime.sendMessage({ action: "stopRecording" });
        updateUI(false, res.stepsCount);
    });

    exportBtn.addEventListener('click', async () => {
        const res = await chrome.runtime.sendMessage({ action: "getSteps" });
        if (res.steps.length === 0) {
            alert('Nenhum passo gravado!');
            return;
        }

        const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(res.steps, null, 2));
        const downloadAnchorNode = document.createElement('a');
        downloadAnchorNode.setAttribute("href", dataStr);
        downloadAnchorNode.setAttribute("download", "passos_automacao.json");
        document.body.appendChild(downloadAnchorNode); // requirido no firefox
        downloadAnchorNode.click();
        downloadAnchorNode.remove();
        
        // Opcional: limpar os passos após exportar?
        // await chrome.runtime.sendMessage({ action: "clearSteps" });
        // updateUI(false, 0);
    });

    function updateUI(isRecording, count) {
        stepCountDisplay.textContent = count;
        
        if (isRecording) {
            startBtn.style.display = 'none';
            stopBtn.style.display = 'block';
            exportBtn.style.display = 'none';
            
            statusText.textContent = 'Gravando...';
            statusText.className = 'status-text recording';
        } else {
            startBtn.style.display = 'block';
            stopBtn.style.display = 'none';
            exportBtn.style.display = count > 0 ? 'block' : 'none';
            
            statusText.textContent = 'Pronto para gravar';
            statusText.className = 'status-text idle';
        }
    }
});
