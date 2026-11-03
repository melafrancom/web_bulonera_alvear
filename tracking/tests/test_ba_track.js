/**
 * test_ba_track.js
 * 
 * QUÉ:
 *   Suite de pruebas para la fachada JavaScript `baTrack` (static/js/ba_track.js).
 * POR QUÉ:
 *   Garantiza que la mitigación de consentimiento en cliente funcione rigurosamente:
 *   - Parseo estricto de cookie `ba_consent` (a=1|d=1).
 *   - Encolamiento pre-consentimiento.
 *   - Vaciado de cola ante consentimiento publicitario.
 *   - Purgado inmediato de cola ante revocación activa (advertising: false).
 *   - Bloqueo de llamadas posteriores a meta() / metaCustom() / ecommerce() / pushGA4().
 *   - Idempotencia ante recepción doble del evento `ba:consent-applied`.
 * CÓMO:
 *   Simula un entorno DOM mínimo (window, document, localStorage, CustomEvent)
 *   y ejecuta aserciones estrictas con el módulo assert de Node.js.
 */

const assert = require('assert');
const fs = require('fs');
const path = require('path');

function createDOMEnvironment() {
    const listeners = {};
    const storage = {};
    let cookieStr = '';

    const docListeners = {};
    const bodyListeners = {};

    const env = {
        window: {
            dataLayer: [],
            addEventListener: function(event, callback) {
                listeners[event] = listeners[event] || [];
                listeners[event].push(callback);
            },
            dispatchEvent: function(event) {
                const cbs = listeners[event.type] || [];
                cbs.forEach(cb => cb(event));
            }
        },
        document: {
            get cookie() {
                return cookieStr;
            },
            set cookie(val) {
                cookieStr = val;
            },
            getElementById: function() { return null; },
            addEventListener: function(event, callback) {
                docListeners[event] = docListeners[event] || [];
                docListeners[event].push(callback);
            },
            dispatchEvent: function(event) {
                const cbs = docListeners[event.type] || [];
                cbs.forEach(cb => cb(event));
            },
            body: {
                addEventListener: function(event, callback) {
                    bodyListeners[event] = bodyListeners[event] || [];
                    bodyListeners[event].push(callback);
                },
                dispatchEvent: function(event) {
                    const cbs = bodyListeners[event.type] || [];
                    cbs.forEach(cb => cb(event));
                }
            }
        },
        localStorage: {
            getItem: function(key) { return storage[key] || null; },
            setItem: function(key, val) { storage[key] = String(val); },
            removeItem: function(key) { delete storage[key]; },
            clear: function() { Object.keys(storage).forEach(k => delete storage[k]); }
        },
        CustomEvent: class {
            constructor(type, init) {
                this.type = type;
                this.detail = (init && init.detail) || null;
            }
        }
    };

    return env;
}

function runTests() {
    console.log("=== Ejecutando Suite de Verificación baTrack (Browser/Mitigación) ===");
    const scriptPath = path.resolve(__dirname, '../../static/js/ba_track.js');
    const scriptCode = fs.readFileSync(scriptPath, 'utf8');

    // TEST 1: Parseo estricto de cookie ba_consent
    {
        console.log("-> Test 1: Parser estricto de cookie ba_consent...");
        const env = createDOMEnvironment();
        env.document.cookie = "ba_consent=a=1|d=1; path=/";
        
        // Ejecutar script en contexto aislado
        const ctxFunction = new Function('window', 'document', 'localStorage', 'CustomEvent', scriptCode);
        ctxFunction(env.window, env.document, env.localStorage, env.CustomEvent);

        const prefs = env.window.baTrack.getConsentPreferences();
        assert.strictEqual(prefs.analytics, true, "Analytics debe ser true con a=1");
        assert.strictEqual(prefs.advertising, true, "Advertising debe ser true con d=1");
        console.log("   PASSED");
    }

    // TEST 2: Descarte estricto pre-consentimiento y encolamiento seguro post-consentimiento
    {
        console.log("-> Test 2: Descarte pre-consentimiento y encolamiento post-consentimiento...");
        const env = createDOMEnvironment();
        const ctxFunction = new Function('window', 'document', 'localStorage', 'CustomEvent', scriptCode);
        ctxFunction(env.window, env.document, env.localStorage, env.CustomEvent);

        const fbqCalls = [];
        env.window.fbq = function(...args) {
            fbqCalls.push(args);
        };

        // 1. Emitir llamada sin consentimiento previo (debe descartarse inmediatamente, cero tracking retroactivo)
        env.window.baTrack.meta('Lead', { cta: 'whatsapp' }, 'lead-pre');
        assert.strictEqual(env.window.baTrack.metaQueue.length, 0, "metaQueue debe estar vacía: eventos pre-consentimiento se descartan");
        assert.strictEqual(fbqCalls.length, 0, "fbq no debe haber sido llamado todavía");

        // 2. Disparar consentimiento publicitario afirmativo (pero simular que fbq está aún cargando en DOM)
        delete env.window.fbq;
        env.window.dispatchEvent(new env.CustomEvent('ba:consent-applied', {
            detail: { analytics: true, advertising: true }
        }));

        // 3. Emitir llamada POST-consentimiento mientras fbq carga asíncronamente (debe encolarse temporalmente)
        env.window.baTrack.meta('Lead', { cta: 'whatsapp' }, 'lead-123');
        assert.strictEqual(env.window.baTrack.metaQueue.length, 1, "metaQueue debe contener 1 evento encolado post-consentimiento");

        // 4. Se carga la librería externa fbq y se vacía la cola
        env.window.fbq = function(...args) {
            fbqCalls.push(args);
        };
        env.window.baTrack.flushMetaQueue();
        assert.strictEqual(env.window.baTrack.metaQueue.length, 0, "metaQueue debe estar vacía tras flush");
        assert.strictEqual(fbqCalls.length, 1, "fbq debe haberse llamado exactamente 1 vez");
        assert.strictEqual(fbqCalls[0][1], 'Lead', "El evento enviado debe ser Lead");
        assert.deepStrictEqual(fbqCalls[0][3], { eventID: 'lead-123' }, "Debe incluir eventID");
        console.log("   PASSED");
    }

    // TEST 3: Purgado inmediato de cola interna, stub de Meta y parada de Clarity ante revocación
    {
        console.log("-> Test 3: Purgado de cola interna, stub fbq.queue y parada de Clarity tras revocación...");
        const env = createDOMEnvironment();
        const ctxFunction = new Function('window', 'document', 'localStorage', 'CustomEvent', scriptCode);
        ctxFunction(env.window, env.document, env.localStorage, env.CustomEvent);

        const fbqCalls = [];
        env.window.fbq = function(...args) {
            fbqCalls.push(args);
        };
        env.window.fbq.queue = [{ event: 'stale_pre_stub' }];

        const clarityCalls = [];
        env.window.clarity = function(...args) {
            clarityCalls.push(args);
        };

        // Otorgar consentimiento pero con fbq ausente para simular encolamiento en carga asíncrona
        delete env.window.fbq;
        env.window.dispatchEvent(new env.CustomEvent('ba:consent-applied', {
            detail: { analytics: true, advertising: true }
        }));

        // Encolar evento post-consentimiento
        env.window.baTrack.meta('AddToCart', { content_id: '123' });
        assert.strictEqual(env.window.baTrack.metaQueue.length, 1, "Evento encolado post-consentimiento");

        // Simular que el stub fbq ahora existe con una cola interna previa
        env.window.fbq = function(...args) {
            fbqCalls.push(args);
        };
        env.window.fbq.queue = [{ event: 'stale_pre_stub' }];

        // Usuario desmarca Publicidad y Analítica en el banner (revocación activa)
        env.window.dispatchEvent(new env.CustomEvent('ba:consent-applied', {
            detail: { analytics: false, advertising: false }
        }));

        // 1. La cola interna de baTrack debe haber sido purgada a 0
        assert.strictEqual(env.window.baTrack.metaQueue.length, 0, "metaQueue DEBE purgarse a 0 ante advertising: false");
        
        // 2. La cola interna del stub de Meta fbq.queue DEBE haber sido purgada a 0
        assert.strictEqual(env.window.fbq.queue.length, 0, "fbq.queue DEBE purgarse a 0 ante advertising: false");
        
        // 3. Debe haberse invocado fbq('consent', 'revoke')
        const consentRevokeCalled = fbqCalls.some(call => call[0] === 'consent' && call[1] === 'revoke');
        assert.strictEqual(consentRevokeCalled, true, "fbq('consent', 'revoke') DEBE ser llamado ante revocación");

        // 4. Clarity debe haber sido detenido con clarity('stop')
        const clarityStopCalled = clarityCalls.some(call => call[0] === 'stop');
        assert.strictEqual(clarityStopCalled, true, "clarity('stop') DEBE ser llamado ante analytics: false");

        // 5. Intentar nueva llamada posterior a meta()
        env.window.baTrack.meta('Purchase', { value: 100 }, 'purchase-456');
        assert.strictEqual(env.window.baTrack.metaQueue.length, 0, "No debe encolar nada tras revocación");
        console.log("   PASSED");
    }

    // TEST 4: Bloqueo de ecommerce y pushGA4 ante revocación de analítica
    {
        console.log("-> Test 4: Bloqueo de analytics (ecommerce y pushGA4) ante analytics: false...");
        const env = createDOMEnvironment();
        const ctxFunction = new Function('window', 'document', 'localStorage', 'CustomEvent', scriptCode);
        ctxFunction(env.window, env.document, env.localStorage, env.CustomEvent);

        // Revocar analítica
        env.window.dispatchEvent(new env.CustomEvent('ba:consent-applied', {
            detail: { analytics: false, advertising: true }
        }));

        env.window.baTrack.ecommerce('purchase', { value: 500 });
        env.window.baTrack.pushGA4({ event: 'custom_page_view' });

        assert.strictEqual(env.window.dataLayer.length, 0, "dataLayer debe permanecer vacío cuando analytics es false");
        console.log("   PASSED");
    }

    // TEST 5: Idempotencia ante recepción doble de ba:consent-applied
    {
        console.log("-> Test 5: Idempotencia ante recepción doble de ba:consent-applied...");
        const env = createDOMEnvironment();
        const ctxFunction = new Function('window', 'document', 'localStorage', 'CustomEvent', scriptCode);
        ctxFunction(env.window, env.document, env.localStorage, env.CustomEvent);

        const fbqCalls = [];

        // Consentimiento previo pero fbq ausente (cargando asíncronamente)
        delete env.window.fbq;
        env.window.dispatchEvent(new env.CustomEvent('ba:consent-applied', {
            detail: { analytics: true, advertising: true }
        }));

        // Encolar evento
        env.window.baTrack.meta('Lead', { cta: 'button' }, 'uuid-1');
        assert.strictEqual(env.window.baTrack.metaQueue.length, 1, "Evento encolado");

        // Se inicializa fbq
        env.window.fbq = function(...args) {
            fbqCalls.push(args);
        };

        // Primer despacho (inmediato al guardar)
        env.window.dispatchEvent(new env.CustomEvent('ba:consent-applied', {
            detail: { analytics: true, advertising: true }
        }));
        env.window.baTrack.flushMetaQueue();
        assert.strictEqual(fbqCalls.length, 1, "Debe haberse ejecutado 1 vez");

        // Segundo despacho (a los 3 segundos tras cargar scripts)
        env.window.dispatchEvent(new env.CustomEvent('ba:consent-applied', {
            detail: { analytics: true, advertising: true }
        }));
        env.window.baTrack.flushMetaQueue();

        assert.strictEqual(fbqCalls.length, 1, "NO DEBE duplicar la llamada tras la segunda emisión");
        console.log("   PASSED");
    }

    // TEST 6: Navegación nativa preservada en enlaces de WhatsApp (Sin popup blocker ni preventDefault)
    {
        console.log("-> Test 6: Preservación de navegación nativa y enriquecimiento de URL en WhatsApp lead...");
        const env = createDOMEnvironment();
        const ctxFunction = new Function('window', 'document', 'localStorage', 'CustomEvent', scriptCode);
        ctxFunction(env.window, env.document, env.localStorage, env.CustomEvent);

        // Inicializar DOMContentLoaded para activar el listener delegado en document.body
        env.document.dispatchEvent(new env.CustomEvent('DOMContentLoaded'));

        const initialHref = '/contact/whatsapp-lead/?text=Hola&source=floating';
        const leadBtn = {
            href: initialHref,
            id: 'floating-whatsapp-btn',
            classList: ['whatsapp-btn'],
            dataset: {
                trackLead: 'whatsapp'
            },
            getAttribute: function(name) {
                if (name === 'data-track-lead') return 'whatsapp';
                if (name === 'href') return this.href;
                return null;
            },
            setAttribute: function(name, val) {
                if (name === 'href') this.href = val;
            },
            closest: function(sel) {
                if (sel.includes('data-ba-lead') || sel.includes('/contact/whatsapp-lead/')) return this;
                return null;
            }
        };

        let preventDefaultCalled = false;
        let windowOpenCalled = false;
        env.window.open = function() {
            windowOpenCalled = true;
        };

        const clickEvent = {
            type: 'click',
            target: leadBtn,
            preventDefault: function() {
                preventDefaultCalled = true;
            }
        };

        // Disparar click en document.body (como sucede en el browser al clickear el botón flotante)
        env.document.body.dispatchEvent(clickEvent);

        assert.strictEqual(preventDefaultCalled, false, "CRÍTICO: preventDefault NO debe ser llamado para evitar bloqueo de popup en móviles");
        assert.strictEqual(windowOpenCalled, false, "CRÍTICO: window.open NO debe ser llamado; el enlace nativo target=_blank realiza la navegación");
        assert.ok(leadBtn.href.startsWith('/contact/whatsapp-lead/?text=Hola&source=floating&event_id='), "leadBtn.href debe haberse enriquecido con event_id para CAPI");

        console.log("   PASSED");
    }

    console.log("=== Todos los tests de baTrack (Browser) pasaron con éxito ===");
}

if (require.main === module) {
    runTests();
}

module.exports = { runTests };
