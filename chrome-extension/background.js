let isRecording = false;
let steps = [];

// Comunicação entre o popup e o content script
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    
    if (request.action === "getState") {
        sendResponse({ isRecording, stepsCount: steps.length });
        return true;
    }

    if (request.action === "startRecording") {
        isRecording = true;
        steps = []; // Inicia uma nova gravação, limpando os passos antigos
        
        // Registra o primeiro passo como navigate (opcional, pega a url da tab atual)
        chrome.tabs.query({active: true, currentWindow: true}, function(tabs) {
            if(tabs[0] && tabs[0].url && !tabs[0].url.startsWith('chrome://')) {
                 steps.push({
                     order: 1,
                     action: "navigate",
                     value: tabs[0].url,
                     description: "Acessar página inicial"
                 });
            }
        });
        
        sendResponse({ isRecording, stepsCount: steps.length });
        return true;
    }

    if (request.action === "stopRecording") {
        isRecording = false;
        sendResponse({ isRecording, stepsCount: steps.length });
        return true;
    }

    if (request.action === "getSteps") {
        sendResponse({ steps: steps });
        return true;
    }

    if (request.action === "clearSteps") {
        steps = [];
        sendResponse({ success: true });
        return true;
    }

    // Recebe novo passo do content.js
    if (request.action === "addStep" && isRecording) {
        const newStep = {
            order: steps.length + 1,
            ...request.stepData
        };
        steps.push(newStep);
        console.log("Novo passo adicionado:", newStep);
        
        // Opcional: salvar no chrome.storage.local pra não perder em caso de fechamento inesperado
        chrome.storage.local.set({ recordedSteps: steps });
    }
});
