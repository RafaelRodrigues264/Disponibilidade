# Dashboard de Disponibilidade de Motoristas

![Dashboard de Disponibilidade](docs/screenshot.png)

Dashboard web em tempo real para gerenciamento de disponibilidade de motoristas, desenvolvido para a transportadora **Novorumo** (Jacareí/SP). Eliminou o controle manual de jornada em planilhas e reduziu o tempo de verificação de disponibilidade de minutos para segundos.

## Como funciona

O sistema tem duas partes:

### 1. Servidor na nuvem (`servidor.py`)
Aplicação Flask hospedada no **Railway** que recebe os dados dos motoristas via API e serve o dashboard para todos os usuários via navegador — sem precisar de nenhuma instalação local.

### 2. Automação local (`automacao_atslog.py`)
Script Python que roda na máquina da empresa e automatiza o processo de exportação das fichas ponto do ATSguiarh e envio ao servidor. Roda em loop contínuo com intervalo configurável (padrão: 30 minutos).

---

## Fluxo completo

```
ATSguiarh (sistema de jornada)
    ↓  automacao_atslog.py faz tudo isso automaticamente:
    ├─ 1. Calcula jornada dos condutores (2 sindicatos)
    ├─ 2. Gera e exporta fichas ponto para Excel
    │       FICHA PONTO - FROTA.xls  (ADI5322 - Novorumo Limeira)
    │       FICHA PONTO - CITRO.xls  (Sindicato Novo - Banco de Horas)
    └─ 3. Envia dados ao servidor → dashboard atualizado
    ↓
Dashboard web (acessível por qualquer pessoa na empresa via navegador)
```

---

## Pré-requisitos

- Python 3.x instalado
- ATSguiarh instalado e aberto na tela principal
- Conta no Railway com o `servidor.py` em execução

### Instalar dependências (uma vez)

```
pip install flask xlrd pyautogui pygetwindow pillow
```

---

## Configuração

### Servidor (Railway)
1. Crie um projeto no Railway com este repositório
2. Configure a variável de ambiente `UPLOAD_TOKEN` com uma senha secreta
3. O Railway sobe o servidor automaticamente via `Procfile`

### Local (`config.txt`)
Crie o arquivo `config.txt` na pasta do projeto (não vai para o GitHub):
```
SERVIDOR_URL=https://seu-app.up.railway.app
TOKEN=sua_senha_aqui
```

### Calibração de coordenadas (`calibrar.py`)
O script de automação clica em botões na tela. As coordenadas padrão são estimativas — você precisa calibrá-las para o seu monitor:

1. Execute `python calibrar.py`
2. Passe o mouse sobre cada botão indicado no script
3. Anote os valores X e Y exibidos
4. Atualize o dicionário `COORDS` no `automacao_atslog.py`

---

## Como usar

### Automação completa (recomendado)
1. Abra o ATSguiarh na **tela principal** (Monitor de Jornada de Trabalho)
2. Deixe o dropdown **Período** da Ficha Ponto Simplificada já na posição correta (mostrando "Últimos 7 dias")
3. Dê duplo clique em `scripts/AUTOMATIZAR.bat`
4. Pressione ENTER quando pedido
5. O script roda sozinho, atualizando o dashboard a cada 30 minutos

> Para cancelar a qualquer momento: mova o mouse para o **canto superior esquerdo** da tela.

### Só enviar os dados (sem automação do ATSguiarh)
Se você exportou as fichas ponto manualmente, rode apenas:
```
scripts/ATUALIZAR.bat
```

---

## Estrutura de arquivos

```
ANALISE DE DISPONIBILIDADE/
├── servidor.py              # Servidor Flask (deploy no Railway)
├── gerar_dados.py           # Lê os Excel e envia ao servidor
├── automacao_atslog.py      # Automação do ATSguiarh (loop contínuo)
├── calibrar.py              # Ferramenta para calibrar coordenadas
├── requirements.txt         # Dependências do servidor (Flask)
├── Procfile                 # Comando de start para o Railway
├── config.txt               # URL e token (não vai ao GitHub)
├── scripts/
│   ├── ATUALIZAR.bat        # Só envia os dados ao servidor
│   └── AUTOMATIZAR.bat      # Roda a automação completa
└── docs/
    └── screenshot.png
```

---

## Regras de negócio

Baseado na **Lei 13.103/2015** (Lei do Motorista):

| Status | Significado |
|--------|-------------|
| 🟢 DISPONÍVEL | Motorista pode ser chamado |
| 🟡 INTERSTÍCIO | Em descanso obrigatório (mínimo 11h entre jornadas) |
| 🔴 EM JORNADA | Jornada em andamento (máximo 12h) |
| ⚫ AFASTADO | De férias, atestado ou outro afastamento |
| ⚪ SEM DADOS | Sem registro no período consultado |

---

## Funcionalidades do dashboard

- Status em tempo real de todos os motoristas da frota
- Cálculo automático de jornada restante e tempo até disponibilidade
- Filtros por status e frota (Jacareí / Limeira)
- Lançamento manual de jornadas (para casos de tablet com defeito)
- Suporte a múltiplos usuários simultâneos via navegador
- Atualização automática a cada 30 segundos
