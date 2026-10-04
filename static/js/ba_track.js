/**
 * baTrack: Bulonera Analytics Facade
 * 
 * Propósito:
 * Resuelve la carga diferida (consentimiento y delay de 3 segundos) mediante un 
 * enfoque orientado a eventos. Encola eventos de Meta Pixel hasta que 
 * _cookie_consent.html emita 'ba:consent-applied'.
 * Inyecta sincrónicamente en dataLayer para GA4/GTM sin polling innecesario.
 */
window.baTrack = window.baTrack || {
    metaQueue: [],
    
    // Función pública para extraer payload renderizado por Django via json_script
    fromScript: function(elementId) {
        try {
            const el = document.getElementById(elementId);
            if (el) {
                return JSON.parse(el.textContent);
            }
        } catch (e) {
            console.error('baTrack: Error parsing json_script ' + elementId, e);
        }
        return null;
    },

    // Función pública para Meta Pixel
    meta: function(eventName, data, eventID) {
        let options = eventID ? { eventID: eventID } : undefined;
        if (typeof fbq === 'function') {
            fbq('track', eventName, data, options);
        } else {
            console.debug("baTrack: fbq no disponible, encolando", eventName);
            this.metaQueue.push({ action: 'track', eventName: eventName, data: data, options: options });
        }
    },
    
    // Función pública para Meta Pixel Custom
    metaCustom: function(eventName, data, eventID) {
        let options = eventID ? { eventID: eventID } : undefined;
        if (typeof fbq === 'function') {
            fbq('trackCustom', eventName, data, options);
        } else {
            console.debug("baTrack: fbq no disponible, encolando custom", eventName);
            this.metaQueue.push({ action: 'trackCustom', eventName: eventName, data: data, options: options });
        }
    },

    // Helper de limpieza para ecommerce (GA4)
    ecommerce: function(eventName, payload) {
        window.dataLayer = window.dataLayer || [];
        window.dataLayer.push({ ecommerce: null });
        if (payload) {
            payload.event = eventName;
            window.dataLayer.push(payload);
        }
    },

    // Función pública directa para GA4 (array nativo)
    pushGA4: function(payload) {
        window.dataLayer = window.dataLayer || [];
        window.dataLayer.push(payload);
    },

    // Vacía la cola cuando se aplican las preferencias
    flushMetaQueue: function() {
        if (typeof fbq === 'function' && this.metaQueue.length > 0) {
            console.debug("baTrack: fbq disponible, vaciando cola Meta");
            while (this.metaQueue.length > 0) {
                const item = this.metaQueue.shift();
                fbq(item.action, item.eventName, item.data, item.options);
            }
        }
    }
};

// Escucha el evento emitido por el banner de consentimiento
window.addEventListener('ba:consent-applied', function(e) {
    const prefs = e.detail;
    if (prefs && prefs.advertising) {
        // Al aplicar consentimiento publicitario, fbq puede tardar unos milisegundos en inicializarse
        // Reintentamos el vaciado de cola Meta unas cuantas veces.
        let attempts = 0;
        let flushInterval = setInterval(() => {
            if (typeof fbq === 'function' || attempts >= 20) {
                clearInterval(flushInterval);
                window.baTrack.flushMetaQueue();
            }
            attempts++;
        }, 200); // Intenta por max 4 segundos
    }
});

// Delegación de leads para botones de WhatsApp (TRK-009)
document.addEventListener('DOMContentLoaded', function() {
    document.body.addEventListener('click', function(e) {
        // Buscar el botón o contenedor más cercano con atributos de lead
        const leadBtn = e.target.closest('[data-ba-lead]') || e.target.closest('a[href*="wa.me"], a[href*="api.whatsapp.com"]');
        if (!leadBtn) return;
        
        const method = leadBtn.getAttribute('data-ba-lead') || 'whatsapp';
        const href = leadBtn.getAttribute('href') || '';
        let sku = '';
        
        try {
            if (href.includes('?text=')) {
                const urlParams = new URLSearchParams(href.split('?')[1]);
                sku = urlParams.get('text') || '';
            }
        } catch (err) {}
        
        const btnId = leadBtn.id || (leadBtn.classList.length ? leadBtn.classList[0] : method);
        
        // Disparar evento para Meta
        window.baTrack.metaCustom('WhatsAppContact', {
            content_name: 'WhatsApp Click',
            content_category: 'Lead Generation',
            cta_id: btnId,
            product_sku: sku
        });
        
        // Disparar evento para GA4
        window.baTrack.pushGA4({
            'event': 'generate_lead',
            'lead_method': method,
            'event_label': btnId,
            'value': 1.0,
            'currency': 'ARS',
            'items': sku ? [{ 'item_id': sku }] : []
        });
    });
});
