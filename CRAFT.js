// Hotkey: Cmd-Shift-P to generate latex & PDF
let pdfMsgId = null;
document.addEventListener('keydown', (e) => { 
  if (e.metaKey && e.shiftKey && e.key === 'p') { 
    e.preventDefault();
    if (pdfMsgId) {
      _post("upsert_msg", {id_: pdfMsgId, msg_type: "code", is_input: 1, content: "import solveit_tex\nawait solveit_tex.current_to_pdf()"
, cmd: "run"});
    } else {
      document.addEventListener("smode:afterSettle", ev => {
        pdfMsgId = ev.detail?.id;
        _post("upsert_msg", {id_: pdfMsgId, msg_type: "code", is_input: 1, content: "import solveit_tex\nawait solveit_tex.current_to_pdf()"
, cmd: "run"});
      }, {once: true});
      _post("add_below", {is_input: 1});
    }
  }
});

