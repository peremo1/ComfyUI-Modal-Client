// Nodo "Informe para copiar": muestra el informe y anade el boton "Copiar informe".
import { app } from "../../scripts/app.js";

async function copiar(texto) {
  try {
    await navigator.clipboard.writeText(texto);
    return true;
  } catch (e) {
    // respaldo para navegadores sin acceso al portapapeles
    const area = document.createElement("textarea");
    area.value = texto;
    document.body.appendChild(area);
    area.select();
    const ok = document.execCommand("copy");
    area.remove();
    return ok;
  }
}

app.registerExtension({
  name: "ChromaPanel.Informe",
  async beforeRegisterNodeDef(nodeType, nodeData) {
    if (nodeData.name !== "ChromaInforme") return;

    const alCrear = nodeType.prototype.onNodeCreated;
    nodeType.prototype.onNodeCreated = function () {
      const r = alCrear?.apply(this, arguments);
      this.informe = "";

      const area = document.createElement("textarea");
      area.readOnly = true;
      area.placeholder = "Pulsa Run: aqui aparecera el informe completo.";
      Object.assign(area.style, {
        width: "100%", height: "100%", fontFamily: "monospace", fontSize: "11px",
        background: "#111", color: "#ddd", border: "1px solid #444", resize: "none",
      });
      this.areaInforme = area;
      if (this.addDOMWidget) {
        this.addDOMWidget("texto_informe", "informe", area, { serialize: false });
      }

      const boton = this.addWidget("button", "Copiar informe", null, async () => {
        if (!this.informe) {
          boton.name = "Todavia no hay informe: pulsa Run";
        } else {
          boton.name = (await copiar(this.informe)) ? "Copiado! Pegalo en el chat" : "No se pudo copiar: selecciona el texto";
        }
        this.setDirtyCanvas(true, true);
        setTimeout(() => { boton.name = "Copiar informe"; this.setDirtyCanvas(true, true); }, 2500);
      });
      boton.serialize = false;
      this.setSize([Math.max(this.size[0], 520), Math.max(this.size[1], 360)]);
      return r;
    };

    const alEjecutar = nodeType.prototype.onExecuted;
    nodeType.prototype.onExecuted = function (mensaje) {
      alEjecutar?.apply(this, arguments);
      const texto = mensaje?.informe?.[0];
      if (texto) {
        this.informe = texto;
        if (this.areaInforme) this.areaInforme.value = texto;
      }
    };
  },
});
