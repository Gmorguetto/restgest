/* Interações da interface:
   1. efeito de onda no ponto onde o botão foi clicado;
   2. botão mostra "enviando" e o formulário não é enviado duas vezes;
   3. janelas de edição que abrem e fecham com animação;
   4. dica flutuante nos gráficos do painel;
   5. busca e filtro do cardápio;
   6. tela cheia na cozinha;
   7. elementos que aparecem ao rolar a página inicial;
   8. números do painel que contam até o valor;
   9. destaque das comandas que acabaram de chegar na cozinha;
   10. avisos podem ser fechados, e os de sucesso somem sozinhos. */
(function () {
  "use strict";

  var movimentoReduzido = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  // 1. Onda no clique
  document.addEventListener("pointerdown", function (evento) {
    var botao = evento.target.closest("button, .botao");
    if (!botao || movimentoReduzido || botao.classList.contains("fechar-aviso")) {
      return;
    }
    var caixa = botao.getBoundingClientRect();
    var tamanho = Math.max(caixa.width, caixa.height);
    var onda = document.createElement("span");
    onda.className = "onda";
    onda.style.width = onda.style.height = tamanho + "px";
    onda.style.left = evento.clientX - caixa.left - tamanho / 2 + "px";
    onda.style.top = evento.clientY - caixa.top - tamanho / 2 + "px";
    botao.appendChild(onda);
    onda.addEventListener("animationend", function () {
      onda.remove();
    });
  });

  // 2. Envio de formulário: mostra o carregamento e bloqueia o segundo clique
  document.addEventListener("submit", function (evento) {
    var formulario = evento.target;
    if (formulario.dataset.enviando) {
      evento.preventDefault();
      return;
    }
    formulario.dataset.enviando = "sim";
    var botao = evento.submitter || formulario.querySelector("button[type=submit]");
    if (botao) {
      botao.classList.add("enviando");
      botao.setAttribute("aria-busy", "true");
    }
  });

  // Ao voltar pelo botão "voltar" do navegador, a página pode vir da memória:
  // libera os formulários de novo.
  window.addEventListener("pageshow", function (evento) {
    if (!evento.persisted) {
      return;
    }
    document.querySelectorAll("form[data-enviando]").forEach(function (formulario) {
      delete formulario.dataset.enviando;
    });
    document.querySelectorAll(".enviando").forEach(function (botao) {
      botao.classList.remove("enviando");
      botao.removeAttribute("aria-busy");
    });
  });

  // 3. Janelas (<dialog>): abrir pelo botão, fechar pelo "Cancelar", pelo "×" ou clicando fora
  function fecharJanela(janela) {
    if (!janela.open) {
      return;
    }
    if (movimentoReduzido) {
      janela.close();
      return;
    }
    var fechada = false;
    function terminar() {
      if (fechada) {
        return;
      }
      fechada = true;
      janela.classList.remove("fechando");
      janela.close();
    }
    janela.classList.add("fechando");
    janela.addEventListener("animationend", function (evento) {
      if (evento.target === janela) {
        terminar();
      }
    });
    // Garantia: fecha mesmo se a animação não terminar (aba em segundo plano, por exemplo)
    window.setTimeout(terminar, 400);
  }

  function abrirJanela(janela) {
    if (!janela || typeof janela.showModal !== "function" || janela.open) {
      return;
    }
    janela.showModal();
    var primeiroCampo = janela.querySelector("input:not([type=hidden]), select");
    if (primeiroCampo) {
      primeiroCampo.focus();
    }
  }

  document.querySelectorAll("[data-abrir]").forEach(function (botao) {
    botao.addEventListener("click", function () {
      abrirJanela(document.getElementById(botao.dataset.abrir));
    });
  });

  document.querySelectorAll("dialog").forEach(function (janela) {
    janela.querySelectorAll("[data-fechar]").forEach(function (botao) {
      botao.addEventListener("click", function () {
        fecharJanela(janela);
      });
    });
    janela.addEventListener("click", function (evento) {
      if (evento.target === janela) {
        fecharJanela(janela);
      }
    });
  });

  // Endereço com #editar-12 (ex.: depois de um erro ao salvar) abre a janela de novo
  if (window.location.hash) {
    var alvo = document.getElementById(window.location.hash.slice(1));
    if (alvo && alvo.tagName === "DIALOG") {
      // Leva a mensagem de erro para dentro da janela, onde ela fica visível
      var erro = document.querySelector(".avisos .aviso-erro");
      var lugar = alvo.querySelector("[data-erro]");
      if (erro && lugar) {
        lugar.textContent = erro.querySelector("span").textContent;
        lugar.hidden = false;
        erro.remove();
      }
      abrirJanela(alvo);
    }
  }

  // 4. Dica flutuante dos gráficos: aparece ao passar o mouse ou focar com o teclado
  var dica = null;
  function mostrarDica(alvo) {
    if (!dica) {
      dica = document.createElement("div");
      dica.className = "dica-flutuante";
      dica.setAttribute("role", "tooltip");
      document.body.appendChild(dica);
    }
    dica.textContent = alvo.dataset.dica;
    var ancora = alvo.querySelector("[data-ancora]") || alvo;
    var caixa = ancora.getBoundingClientRect();
    if (caixa.height === 0) {
      caixa = alvo.getBoundingClientRect();
      dica.style.top = caixa.bottom + window.scrollY - 4 + "px";
    } else {
      dica.style.top = caixa.top + window.scrollY + "px";
    }
    dica.style.left = caixa.left + caixa.width / 2 + window.scrollX + "px";
    dica.classList.add("visivel");
  }
  function esconderDica() {
    if (dica) {
      dica.classList.remove("visivel");
    }
  }
  ["mouseover", "focusin"].forEach(function (tipo) {
    document.addEventListener(tipo, function (evento) {
      var alvo = evento.target.closest && evento.target.closest("[data-dica]");
      if (alvo) {
        mostrarDica(alvo);
      }
    });
  });
  ["mouseout", "focusout"].forEach(function (tipo) {
    document.addEventListener(tipo, function (evento) {
      if (evento.target.closest && evento.target.closest("[data-dica]")) {
        esconderDica();
      }
    });
  });

  // 5. Cardápio: busca por nome e filtro por categoria, sem recarregar a página
  var filtro = document.querySelector("[data-filtro-cardapio]");
  if (filtro) {
    var busca = filtro.querySelector("[data-busca]");
    var chips = filtro.querySelectorAll("[data-chip]");
    var semResultado = document.querySelector("[data-sem-resultado]");
    var escolhido = "todas";
    var semAcento = function (texto) {
      return texto.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
    };
    var aplicarFiltro = function () {
      var termo = semAcento(busca.value.trim());
      var visiveis = 0;
      document.querySelectorAll("[data-categoria]").forEach(function (secao) {
        var daCategoria = escolhido === "todas" || escolhido === "indisponiveis" || secao.dataset.categoria === escolhido;
        var linhasVisiveis = 0;
        secao.querySelectorAll("tr[data-nome]").forEach(function (linha) {
          var mostra = daCategoria
            && (!termo || semAcento(linha.dataset.nome).indexOf(termo) !== -1)
            && (escolhido !== "indisponiveis" || linha.dataset.ativo === "0");
          linha.hidden = !mostra;
          if (mostra) {
            linhasVisiveis += 1;
          }
        });
        var filtrando = termo || escolhido !== "todas";
        secao.hidden = !daCategoria || (filtrando && linhasVisiveis === 0);
        visiveis += linhasVisiveis;
      });
      if (semResultado) {
        semResultado.hidden = visiveis > 0;
      }
    };
    busca.addEventListener("input", aplicarFiltro);
    chips.forEach(function (chip) {
      chip.addEventListener("click", function () {
        escolhido = chip.dataset.chip;
        chips.forEach(function (outro) {
          var ativo = outro === chip;
          outro.classList.toggle("ativo", ativo);
          outro.setAttribute("aria-pressed", ativo ? "true" : "false");
        });
        // "Novo produto" já vem na categoria escolhida
        var selecao = document.querySelector("#novo-produto [data-categoria-padrao]");
        if (selecao && /^\d+$/.test(escolhido)) {
          selecao.value = escolhido;
        }
        aplicarFiltro();
      });
    });
  }

  // 6. Cozinha: tela cheia para a TV
  var botaoTelaCheia = document.querySelector("[data-tela-cheia]");
  if (botaoTelaCheia && document.documentElement.requestFullscreen) {
    botaoTelaCheia.addEventListener("click", function () {
      if (document.fullscreenElement) {
        document.exitFullscreen();
      } else {
        document.body.requestFullscreen();
      }
    });
  } else if (botaoTelaCheia) {
    botaoTelaCheia.hidden = true;
  }

  // 7. Elementos que aparecem suavemente quando entram na tela (página inicial)
  var revelaveis = document.querySelectorAll(".revelar");
  if (revelaveis.length && "IntersectionObserver" in window && !movimentoReduzido) {
    var observador = new IntersectionObserver(function (entradas) {
      entradas.forEach(function (entrada) {
        if (entrada.isIntersecting) {
          entrada.target.classList.add("visivel");
          observador.unobserve(entrada.target);
        }
      });
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.12 });
    revelaveis.forEach(function (elemento) { observador.observe(elemento); });
  } else {
    revelaveis.forEach(function (elemento) { elemento.classList.add("visivel"); });
  }

  // 8. Números do painel contam até o valor (a partir do valor da última visita)
  var formatoReais = new Intl.NumberFormat("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  document.querySelectorAll("[data-contar]").forEach(function (elemento) {
    var final = Number(elemento.dataset.contar);
    var moeda = elemento.dataset.formato === "moeda";
    var textoFinal = elemento.textContent;
    var chave = "contar:" + location.pathname + ":" + elemento.dataset.chave;
    var anterior = null;
    try {
      anterior = sessionStorage.getItem(chave);
      sessionStorage.setItem(chave, String(final));
    } catch (erro) { /* navegação privada: anima a partir do zero */ }
    var inicio = anterior === null ? 0 : Number(anterior);
    if (movimentoReduzido || isNaN(final) || isNaN(inicio) || inicio === final) {
      return;
    }
    var comeco = null;
    var duracao = 900;
    function quadro(agora) {
      if (comeco === null) {
        comeco = agora;
      }
      var progresso = Math.min((agora - comeco) / duracao, 1);
      var valor = Math.round(inicio + (final - inicio) * (1 - Math.pow(1 - progresso, 3)));
      elemento.textContent = progresso < 1
        ? (moeda ? "R$ " + formatoReais.format(valor / 100) : String(valor))
        : textoFinal;
      if (progresso < 1) {
        requestAnimationFrame(quadro);
      }
    }
    requestAnimationFrame(quadro);
  });

  // 9. Cozinha: destaca as comandas que chegaram desde a última atualização
  var novas = document.querySelectorAll("[data-comanda-nova]");
  if (document.body.classList.contains("tela-cozinha")) {
    var vistas = null;
    try {
      vistas = JSON.parse(sessionStorage.getItem("cozinha:vistas") || "null");
      sessionStorage.setItem("cozinha:vistas", JSON.stringify(
        Array.prototype.map.call(novas, function (c) { return c.dataset.comandaNova; })
      ));
    } catch (erro) { vistas = null; }
    if (vistas) {
      novas.forEach(function (comanda) {
        if (vistas.indexOf(comanda.dataset.comandaNova) === -1) {
          comanda.classList.add("chegou");
          var selo = document.createElement("span");
          selo.className = "selo-chegou";
          selo.textContent = "Chegou agora";
          comanda.querySelector("h3").appendChild(selo);
        }
      });
    }
  }

  // 10. Avisos
  function fecharAviso(aviso) {
    if (movimentoReduzido) {
      aviso.remove();
      return;
    }
    aviso.classList.add("saindo");
    aviso.addEventListener("animationend", function () {
      aviso.remove();
    }, { once: true });
    window.setTimeout(function () {
      aviso.remove();
    }, 500);
  }

  document.querySelectorAll("[data-fechavel]").forEach(function (aviso) {
    var botao = aviso.querySelector(".fechar-aviso");
    if (botao) {
      botao.addEventListener("click", function () {
        fecharAviso(aviso);
      });
    }
    if (aviso.classList.contains("aviso-ok")) {
      window.setTimeout(function () {
        if (aviso.isConnected) {
          fecharAviso(aviso);
        }
      }, 6000);
    }
  });
})();
