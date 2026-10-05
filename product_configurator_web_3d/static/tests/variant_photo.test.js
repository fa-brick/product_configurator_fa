/**
 * variant_photo.test.js — La photo d'une variante née de la confirmation (D-399, lot 5).
 *
 * La règle qui compte : **une image perdue n'empêche jamais un achat.** Tout tient dans un
 * budget ; un viewer qui ne répond pas, une route qui traîne ou qui lève, et l'on repart
 * vers le panier sans l'image. Et rien ne part quand le serveur n'a rien demandé.
 *
 * Harnais : une page de papier ; le « viewer » répond aux demandes posées dans
 * `state.photoRequest` par `photoCaptured`, comme le vrai par `onThumbnailCaptured`.
 */
import {
    capturePhoto, photoCaptured, sendVariantPhoto, withTimeout,
} from "../src/page/variant_photo.js";

const PHOTO = { pose: { azimuth: 0, inclination: 60, distance: 300 }, size: 1024 };

function page({ answers = ["IMG"], route = async () => ({ ok: true }), isolated = false } = {}) {
    const calls = [];
    const selects = [];
    const replies = [...answers];
    const self = {
        state: { selection: { nodeId: isolated ? "n1" : null, isolated } },
        _select(nodeId, iso) { selects.push([nodeId, iso]); },
        async _call(path, params) { calls.push([path, params]); return route(path, params); },
    };
    let request = null;
    Object.defineProperty(self.state, "photoRequest", {
        get: () => request,
        set(req) {
            request = req;
            if (!req) return;
            const reply = replies.length ? replies.shift() : undefined;
            if (reply === undefined) return;          // le viewer se tait
            setTimeout(() => photoCaptured(self, reply), 0);
        },
    });
    return { self, calls, selects };
}

describe("withTimeout", () => {
    test("rend la valeur si elle arrive à temps, `null` sinon", async () => {
        expect(await withTimeout(Promise.resolve(7), 100)).toBe(7);
        expect(await withTimeout(new Promise(() => {}), 10)).toBe(null);
    });
});

describe("capturePhoto / photoCaptured", () => {
    test("la demande part dans l'état, la réponse revient à la promesse", async () => {
        const { self } = page();
        const b64 = await capturePhoto(self, PHOTO);
        expect(b64).toBe("IMG");
        expect(self.state.photoRequest).toBe(null);
    });
});

describe("sendVariantPhoto", () => {
    test("photographie, puis envoie l'image de SA variante", async () => {
        const { self, calls } = page();
        expect(await sendVariantPhoto(self, PHOTO, 42)).toBe(true);
        expect(calls).toEqual([["/configurator/variant_image", { product_id: 42, image: "IMG" }]]);
    });

    test("rien demandé par le serveur : rien ne part", async () => {
        const { self, calls } = page();
        expect(await sendVariantPhoto(self, null, 42)).toBe(false);
        expect(await sendVariantPhoto(self, PHOTO, null)).toBe(false);
        expect(calls).toHaveLength(0);
    });

    test("le viewer décline d'abord (textures en vol) : on redemande, dans le budget", async () => {
        const { self, calls } = page({ answers: [null, null, "IMG"] });
        expect(await sendVariantPhoto(self, PHOTO, 42)).toBe(true);
        expect(calls).toHaveLength(1);
    });

    test("⚠️ le viewer se tait : on rend la main dans le budget, sans image", async () => {
        const { self, calls } = page({ answers: [] });
        const t0 = Date.now();
        expect(await sendVariantPhoto(self, PHOTO, 42, { budget: 300 })).toBe(false);
        expect(Date.now() - t0).toBeLessThan(1500);
        expect(calls).toHaveLength(0);
        expect(self.state.photoRequest).toBe(null);
    });

    test("⚠️ la route lève : pas d'exception jusqu'au panier", async () => {
        const { self } = page({ route: async () => { throw new Error("réseau"); } });
        const warn = jest.spyOn(console, "warn").mockImplementation(() => {});
        await expect(sendVariantPhoto(self, PHOTO, 42)).resolves.toBe(false);
        warn.mockRestore();
    });

    test("un refus du serveur se rend comme un échec, sans plus", async () => {
        const { self } = page({ route: async () => ({ error: "not_wanted" }) });
        expect(await sendVariantPhoto(self, PHOTO, 42)).toBe(false);
    });

    test("une pièce ISOLÉE est rendue à la scène entière avant la photo", async () => {
        const { self, selects } = page({ isolated: true });
        await sendVariantPhoto(self, PHOTO, 42);
        expect(selects).toEqual([[null, false]]);
    });
});
