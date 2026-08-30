import { app } from "../../scripts/app.js";

const SPECS = {
    MiniMaxH3StreamLiveExtensionAVToVHS: {
        prefix: "extension_",
        maxInputs: 64,
        defaultInputs: 6,
    },
    MiniMaxH3StreamLiveMusicVideoToVHS: {
        prefix: "clip_",
        maxInputs: 64,
        defaultInputs: 20,
    },
};

function specFor(node) {
    const name = node?.comfyClass ?? node?.type;
    return SPECS[name] ?? null;
}

function inputCountWidget(node) {
    return node?.widgets?.find((w) => w.name === "input_count") ?? null;
}

function desiredInputCount(node, spec) {
    const raw = Number(inputCountWidget(node)?.value ?? spec.defaultInputs);
    if (!Number.isFinite(raw)) return spec.defaultInputs;
    return Math.max(1, Math.min(spec.maxInputs, Math.trunc(raw)));
}

function dynamicNumber(input, spec) {
    const name = String(input?.name ?? "");
    if (!name.startsWith(spec.prefix)) return null;
    const raw = name.slice(spec.prefix.length);
    return /^\d+$/.test(raw) ? Number(raw) : null;
}

function reconcileDynamicInputs(node) {
    const spec = specFor(node);
    if (!spec || !Array.isArray(node.inputs)) return;
    const wanted = desiredInputCount(node, spec);

    // Remove excess dynamic sockets from the end so existing lower-numbered
    // connections stay intact. LiteGraph disconnects removed sockets cleanly.
    for (let i = node.inputs.length - 1; i >= 0; i--) {
        const n = dynamicNumber(node.inputs[i], spec);
        if (n != null && n > wanted) {
            if (node.inputs?.[i]?.link != null) node.disconnectInput?.(i);
            node.removeInput(i);
        }
    }

    const present = new Set(
        node.inputs.map((input) => dynamicNumber(input, spec)).filter((n) => n != null)
    );
    for (let i = 1; i <= wanted; i++) {
        if (!present.has(i)) {
            node.addInput(`${spec.prefix}${i}`, "LATENT", { shape: 7 });
        }
    }

    node.setSize?.(node.computeSize?.() ?? node.size);
    node.setDirtyCanvas?.(true, true);
}

function ensureUpdateButton(node) {
    if (!specFor(node) || node._h3DynamicStreamButton) return;
    const button = node.addWidget?.(
        "button",
        "Update inputs",
        null,
        () => reconcileDynamicInputs(node)
    );
    if (button) {
        button.serialize = false;
        button.options ??= {};
        button.options.serialize = false;
        node._h3DynamicStreamButton = button;
    }
}

app.registerExtension({
    name: "H3.DynamicStreamInputs",

    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (!SPECS[nodeData?.name]) return;

        const originalCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function(...args) {
            const result = originalCreated?.apply(this, args);
            ensureUpdateButton(this);
            reconcileDynamicInputs(this);
            return result;
        };

        const originalConfigure = nodeType.prototype.onConfigure;
        nodeType.prototype.onConfigure = function(info, ...args) {
            const result = originalConfigure?.call(this, info, ...args);
            // Reconcile synchronously so saved dynamic links can attach during
            // the graph's normal link-restoration pass.
            ensureUpdateButton(this);
            reconcileDynamicInputs(this);
            return result;
        };
    },
});
