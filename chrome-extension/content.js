// Função auxiliar para obter um seletor CSS simples de um elemento
function getCssSelector(el) {
    if (el.id) {
        return `#${el.id}`;
    }
    if (el.className && typeof el.className === 'string') {
        const classes = el.className.trim().split(/\s+/);
        if (classes.length > 0 && classes[0] !== '') {
            return `${el.tagName.toLowerCase()}.${classes.join('.')}`;
        }
    }
    
    // Fallback: tag + atributos importantes caso não tenha id ou classe útil
    let selector = el.tagName.toLowerCase();
    if(el.name) selector += `[name="${el.name}"]`;
    if(el.type && el.tagName === 'INPUT') selector += `[type="${el.type}"]`;
    if(el.placeholder) selector += `[placeholder="${el.placeholder}"]`;
    if(el.innerText && el.innerText.length < 30) {
       // Apenas dicas, raramente vamos usar para automacao solida, mas ajuda
    }
    
    // Tenta pegar nth-child se for muito generico
    if(selector === el.tagName.toLowerCase() && el.parentNode) {
         const children = Array.from(el.parentNode.children);
         const index = children.indexOf(el);
         if(index > -1) {
             selector += `:nth-child(${index + 1})`;
         }
    }

    return selector;
}

// Obter um texto curto descritivo para o clique
function getElementDescription(el) {
    let text = el.innerText || el.value || el.title || el.placeholder;
    if (!text && el.tagName.toLowerCase() === 'img') text = el.alt;
    
    if (text) {
        text = text.trim();
        if (text.length > 30) text = text.substring(0, 30) + "...";
        return `Clique em '${text}'`;
    }
    return `Clique em ${el.tagName.toLowerCase()}`;
}

// Intercepta Clipes
document.addEventListener('click', async (e) => {
    // Verifica primeiro se a extensão está gravando
    try {
        chrome.runtime.sendMessage({ action: "getState" }, (response) => {
            if (response && response.isRecording) {
                // Só grava cliques em interações que normalmente importam (A, BUTTON, INPUT, etc ou se tiver classe indicando que é clicável)
                let target = e.target;
                
                // Sobe na arvore caso clique dentro de um botão complexo (ex: icone dentro de <button>)
                while(target && target.tagName !== 'BUTTON' && target.tagName !== 'A' && target.tagName !== 'INPUT' && target.tagName !== 'BODY') {
                    if(target.onclick || target.getAttribute('role') === 'button' || target.style.cursor === 'pointer') {
                        break;
                    }
                    target = target.parentNode;
                }
                
                if (!target || target.tagName === 'BODY' || target.tagName === 'HTML') return;
                
                // Se for um input de texto, ignoramos click, deixamos pra pegar no evento de input/change. Só pegamos se for checkbox/radio/submit
                if (target.tagName === 'INPUT') {
                    const type = target.type.toLowerCase();
                    if (type === 'text' || type === 'password' || type === 'email' || type === 'number' || type === 'search' || type === 'tel') {
                        return; // Deixa pro listener de 'change'
                    }
                }

                const selector = getCssSelector(target);
                const description = getElementDescription(target);

                chrome.runtime.sendMessage({
                    action: "addStep",
                    stepData: {
                        action: "click",
                        selector: selector,
                        description: description,
                        waitTime: 1000 // default wait pra evitar race conditions básicos
                    }
                });
            }
        });
    } catch(err) {
        // Ignora erro se a extensão tiver sido recarregada ou estiver offline
    }
}, true); // Use capture phase para tentar pegar antes de possíveis stopPropagation


// Intercepta Mudanças em Inputs e Selects
document.addEventListener('change', async (e) => {
    try {
        chrome.runtime.sendMessage({ action: "getState" }, (response) => {
            if (response && response.isRecording) {
                const target = e.target;
                if (!target || (target.tagName !== 'INPUT' && target.tagName !== 'TEXTAREA' && target.tagName !== 'SELECT')) return;

                const type = target.tagName === 'INPUT' ? target.type.toLowerCase() : target.tagName.toLowerCase();
                
                // Ignorar checkbox/radio aqui pois já pegamos no click
                if(type === 'checkbox' || type === 'radio') return;

                const selector = getCssSelector(target);
                const value = target.value;
                const fieldName = target.name || target.id || target.placeholder || "campo";
                const description = `Preencher ${fieldName} com '${value}'`;

                chrome.runtime.sendMessage({
                    action: "addStep",
                    stepData: {
                        action: "type",
                        selector: selector,
                        value: value,
                        description: description,
                        waitTime: 1000
                    }
                });
            }
        });
    } catch(err) {
    }
}, true);
