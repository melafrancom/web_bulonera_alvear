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
            addEventListener: function() {},
            body: { addEventListener: function() {} }
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

    // TEST 2: Encolamiento pre-consentimiento y vaciado seguro
    {
        console.log("-> Test 2: Encolamiento de eventos Meta y vaciado tras consentimiento...");
        const env = createDOMEnvironment();
        const ctxFunction = new Function('window', 'document', 'localStorage', 'CustomEvent', scriptCode);
        ctxFunction(env.window, env.document, env.localStorage, env.CustomEvent);

        const fbqCalls = [];
        env.window.fbq = function(...args) {
            fbqCalls.push(args);
        };

        // Emitir llamada sin consentimiento previo (debe encolarse)
        env.window.baTrack.meta('Lead', { cta: 'whatsapp' }, 'lead-123');
        assert.strictEqual(env.window.baTrack.metaQueue.length, 1, "metaQueue debe contener 1 evento encolado");
        assert.strictEqual(fbqCalls.length, 0, "fbq no debe haber sido llamado todavía");

        // Disparar consentimiento publicitario
        env.window.dispatchEvent(new env.CustomEvent('ba:consent-applied', {
            detail: { analytics: true, advertising: true }
        }));

        // Esperar vaciado o forzar flush
        env.window.baTrack.flushMetaQueue();
        assert.strictEqual(env.window.baTrack.metaQueue.length, 0, "metaQueue debe estar vacía tras flush");
        assert.strictEqual(fbqCalls.length, 1, "fbq debe haberse llamado exactamente 1 vez");
        assert.strictEqual(fbqCalls[0][1], 'Lead', "El evento enviado debe ser Lead");
        assert.deepStrictEqual(fbqCalls[0][3], { eventID: 'lead-123' }, "Debe incluir eventID");
        console.log("   PASSED");
    }

    // TEST 3: Purgado inmediato de cola y bloqueo ante revocación activa (advertising: false)
    {
        console.log("-> Test 3: Purgado de cola y bloqueo total tras revocación de publicidad...");
        const env = createDOMEnvironment();
        const ctxFunction = new Function('window', 'document', 'localStorage', 'CustomEvent', scriptCode);
        ctxFunction(env.window, env.document, env.localStorage, env.CustomEvent);

        const fbqCalls = [];
        env.window.fbq = function(...args) {
            fbqCalls.push(args);
        };

        // Encolar evento inicial
        env.window.baTrack.meta('AddToCart', { content_id: '123' });
        assert.strictEqual(env.window.baTrack.metaQueue.length, 1, "Evento encolado");

        // Usuario desmarca Publicidad y guarda en el banner (revocación activa)
        env.window.dispatchEvent(new env.CustomEvent('ba:consent-applied', {
            detail: { analytics: true, advertising: false }
        }));

        // La cola debe haber sido purgada de inmediato
        assert.strictEqual(env.window.baTrack.metaQueue.length, 0, "metaQueue DEBE purgarse a 0 ante advertising: false");

        // Intentar nueva llamada posterior a meta()
        env.window.baTrack.meta('Purchase', { value: 100 }, 'purchase-456');
        assert.strictEqual(env.window.baTrack.metaQueue.length, 0, "No debe encolar nada tras revocación");
        assert.strictEqual(fbqCalls.length, 0, "fbq no debe ser llamado tras revocación");
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
        env.window.fbq = function(...args) {
            fbqCalls.push(args);
        };

        // Encolar evento
        env.window.baTrack.meta('Lead', { cta: 'button' }, 'uuid-1');

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

    console.log("=== Todos los tests de baTrack (Browser) pasaron con éxito ===");
}

if (require.main === module) {
    runTests();
}

module.exports = { runTests };
