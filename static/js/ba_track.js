/**
 * baTrack: Bulonera Analytics Facade
 * 
 * Propósito:
 * Resuelve la carga diferida (consentimiento y delay de 3 segundos) mediante un 
 * enfoque orientado a eventos y respeta la revocación activa de consentimientos en la ventana abierta.
 * Encola eventos de Meta Pixel hasta que _cookie_consent.html emita 'ba:consent-applied'.
 * Bloquea emisiones si el usuario revoca o no otorga consentimiento para analítica o publicidad.
 * Inyecta sincrónicamente en dataLayer para GA4/GTM solo si el consentimiento analítico está activo.
 */
window.baTrack = window.baTrack || {
    metaQueue: [],
    _prefs: null,

    // Helper interno para obtener la función fbq (window.fbq o identificador libre)
    _getFbq: function() {
        if (typeof window !== 'undefined' && typeof window.fbq === 'function') {
            return window.fbq;
        }
        if (typeof fbq === 'function') {
            return fbq;
        }
        return null;
    },

    // Parser estricto por clave-valor para la cookie ba_consent (a=1|d=1) o localStorage
    getConsentPreferences: function() {
        if (this._prefs !== null) {
            return this._prefs;
        }
        try {
            // 1. Intentar desde localStorage
            const stored = localStorage.getItem('ba_cookie_consent');
            if (stored) {
                this._prefs = JSON.parse(stored);
                return this._prefs;
            }
            // 2. Intentar desde document.cookie (formato estricto clave-valor: a=1|d=1)
            const match = document.cookie.match(/(?:^|;\s*)ba_consent=([^;]+)/);
            if (match) {
                const raw = decodeURIComponent(match[1]);
                const parsed = { analytics: false, advertising: false };
                raw.split('|').forEach(function(part) {
                    const kv = part.split('=');
                    if (kv.length === 2) {
                        const key = kv[0].trim();
                        const val = kv[1].trim();
                        if (key === 'a' && val === '1') parsed.analytics = true;
                        if (key === 'd' && val === '1') parsed.advertising = true;
                    }
                });
                this._prefs = parsed;
                return this._prefs;
            }
        } catch (e) {
            console.error('baTrack: Error parsing consent preferences', e);
        }
        // Sin preferencias registradas aún (banner pendiente)
        return { analytics: null, advertising: null };
    },

    // Actualiza preferencias en memoria (usado internamente por el event listener)
    setPreferences: function(prefs) {
        this._prefs = prefs;
        if (prefs && prefs.advertising === false) {
            // Si el usuario revoca o rechaza publicidad, purga la cola inmediatamente
            this.metaQueue = [];
            console.debug("baTrack: Consentimiento de publicidad revocado/rechazado. Cola Meta purgada.");
        }
    },

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
        const prefs = this.getConsentPreferences();
        // Si el usuario rechazó o revocó publicidad explícitamente, abortar
        if (prefs.advertising === false) {
            console.debug("baTrack: Publicidad no consentida, descartando Meta event:", eventName);
            return;
        }

        const _fbq = this._getFbq();
        let options = eventID ? { eventID: eventID } : undefined;
        if (_fbq && prefs.advertising === true) {
            _fbq('track', eventName, data, options);
        } else {
            console.debug("baTrack: fbq no disponible o consentimiento pendiente, encolando", eventName);
            this.metaQueue.push({ action: 'track', eventName: eventName, data: data, options: options });
        }
    },
    
    // Función pública para Meta Pixel Custom
    metaCustom: function(eventName, data, eventID) {
        const prefs = this.getConsentPreferences();
        if (prefs.advertising === false) {
            console.debug("baTrack: Publicidad no consentida, descartando Meta custom event:", eventName);
            return;
        }

        const _fbq = this._getFbq();
        let options = eventID ? { eventID: eventID } : undefined;
        if (_fbq && prefs.advertising === true) {
            _fbq('trackCustom', eventName, data, options);
        } else {
            console.debug("baTrack: fbq no disponible o consentimiento pendiente, encolando custom", eventName);
            this.metaQueue.push({ action: 'trackCustom', eventName: eventName, data: data, options: options });
        }
    },

    // Helper de limpieza para ecommerce (GA4)
    ecommerce: function(eventName, payload) {
        const prefs = this.getConsentPreferences();
        if (prefs.analytics === false) {
            console.debug("baTrack: Analítica no consentida, descartando ecommerce event:", eventName);
            return;
        }

        window.dataLayer = window.dataLayer || [];
        window.dataLayer.push({ ecommerce: null });
        if (payload) {
            const ecommerceObj = payload.ecommerce || payload;
            window.dataLayer.push({
                event: eventName,
                value: ecommerceObj.value,
                currency: ecommerceObj.currency,
                ecommerce: ecommerceObj
            });
        }
    },

    // Función pública directa para GA4 (array nativo)
    pushGA4: function(payload) {
        const prefs = this.getConsentPreferences();
        if (prefs.analytics === false) {
            console.debug("baTrack: Analítica no consentida, descartando GA4 push:", payload);
            return;
        }

        window.dataLayer = window.dataLayer || [];
        window.dataLayer.push(payload);
    },

    // Vacía la cola cuando se aplican las preferencias
    flushMetaQueue: function() {
        const prefs = this.getConsentPreferences();
        if (prefs.advertising === false) {
            this.metaQueue = [];
            return;
        }
        const _fbq = this._getFbq();
        if (_fbq && this.metaQueue.length > 0) {
            console.debug("baTrack: fbq disponible, vaciando cola Meta");
            while (this.metaQueue.length > 0) {
                const item = this.metaQueue.shift();
                _fbq(item.action, item.eventName, item.data, item.options);
            }
        }
    }
};

// Escucha el evento emitido por el banner de consentimiento
window.addEventListener('ba:consent-applied', function(e) {
    const prefs = e.detail;
    if (prefs) {
        window.baTrack.setPreferences(prefs);
        if (prefs.advertising) {
            // Al aplicar consentimiento publicitario, fbq puede tardar unos milisegundos en inicializarse
            // Reintentamos el vaciado de cola Meta unas cuantas veces.
            let attempts = 0;
            let flushInterval = setInterval(() => {
                const _fbq = window.baTrack._getFbq();
                if (_fbq || attempts >= 20) {
                    clearInterval(flushInterval);
                    window.baTrack.flushMetaQueue();
                }
                attempts++;
            }, 200); // Intenta por max 4 segundos
        }
    }
});

// Helper para generar UUIDs (RFC4122) para deduplicación
function uuidv4() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
        var r = Math.random() * 16 | 0, v = c == 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}

// Delegación de leads para botones de WhatsApp (TRK-009)
document.addEventListener('DOMContentLoaded', function() {
    document.body.addEventListener('click', function(e) {
        // Buscar el botón o contenedor más cercano con atributos de lead
        const leadBtn = e.target.closest('[data-ba-lead]') || e.target.closest('a[href*="wa.me"], a[href*="api.whatsapp.com"], a[href*="/contact/whatsapp-lead/"]');
        if (!leadBtn) return;
        
        const method = leadBtn.getAttribute('data-ba-lead') || 'whatsapp';
        let href = leadBtn.getAttribute('href') || '';
        let sku = '';
        
        try {
            if (href.includes('?text=')) {
                const urlParams = new URLSearchParams(href.split('?')[1]);
                sku = urlParams.get('text') || '';
            }
        } catch (err) {}
        
        const btnId = leadBtn.id || (leadBtn.classList.length ? leadBtn.classList[0] : method);
        const eventId = uuidv4();
        
        // Disparar evento estándar Lead para Meta con deduplicación (eventID)
        // OBLIGATORIO: Debe coincidir exactamente con el evento 'Lead' emitido por CAPI
        window.baTrack.meta('Lead', {
            content_name: 'WhatsApp Click',
            content_category: 'Lead Generation',
            cta_id: btnId,
            product_sku: sku
        }, eventId);
        
        // Disparar evento para GA4
        window.baTrack.pushGA4({
            'event': 'generate_lead',
            'lead_method': method,
            'event_label': btnId,
            'value': 1.0,
            'currency': 'ARS',
            'items': sku ? [{ 'item_id': sku }] : []
        });
        
        // CAPI Híbrido: Si el botón apunta a nuestra vista interna de redirección, 
        // inyectamos el event_id en la URL para que el backend deduplique.
        if (href.includes('/contact/whatsapp-lead/')) {
            e.preventDefault(); // Detenemos la navegación nativa
            const connector = href.includes('?') ? '&' : '?';
            // Abrimos la ruta interna (que registra el CAPI y redirige a wa.me)
            window.open(href + connector + 'event_id=' + eventId, leadBtn.target || '_blank');
        }
    });
});
