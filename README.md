# Site de animes da temporada

Site estático que lista os animes que você acompanha, com ficha técnica, próximo episódio e análise escrita por você. Uma atualização consulta o AniList, regenera só as páginas que mudaram e, quando uma data de estreia muda, registra um aviso.

## O que está nesta pasta

- `scripts/update.py`: o script de atualização e geração das páginas.
- `data/animes.json`: sua lista de animes e os textos editoriais (análise, nota, fonte oficial).
- `data/estado.json`, `data/pendentes.json`, `data/avisos.json`: gerados pelo script. Não edite à mão.
- `docs/`: o site gerado. O GitHub Pages publica essa pasta.
- `.github/workflows/atualizar.yml`: roda a atualização toda segunda e quinta, e também pelo botão manual.

## Passo a passo para colocar no ar

1. Crie uma conta no GitHub, se ainda não tiver, e um repositório novo, público, com o nome que quiser (por exemplo, `animes-temporada`).
2. Envie esta pasta para o repositório. Pelo navegador, use "Add file > Upload files" e arraste os arquivos, ou use o Git pelo terminal, se já souber usar.
3. Em "Settings > Actions > General", deixe marcada a opção de permissão de leitura e escrita para o `GITHUB_TOKEN`, para que o workflow consiga fazer o commit.
4. Em "Settings > Pages", escolha "Deploy from a branch", branch `main` e pasta `/docs`. O site ficará em um endereço do tipo `seu-usuario.github.io/animes-temporada`.
5. Teste localmente, se quiser, rodando `python scripts/update.py` na sua máquina. Não precisa instalar nada, o script usa só a biblioteca padrão do Python 3.9 ou mais recente.
6. Vá na aba "Actions", escolha "Atualizar site de animes" e clique em "Run workflow" para a primeira execução. Ela leva poucos minutos.
7. Confira os IDs de cada anime. A busca por nome pode pegar a obra errada, especialmente em casos como "Dragon Ball Super", que tem várias versões. Abra o site do AniList de cada um, copie o número que aparece na URL (por exemplo, `anilist.co/anime/12345`) e coloque em `anilist_id` no `animes.json`, sem aspas. Depois rode de novo.
8. Quando escrever uma análise, coloque o texto em `analise` no `animes.json`, com parágrafos separados por uma linha em branco, e a nota de 0 a 10 em `nota`. Ao rodar a atualização, a página é regenerada com o texto novo.

## Como funcionam os avisos de data

Quando o AniList mostra que a estreia de um episódio mudou, o script faz uma de duas coisas. Se o anime tiver `fonte_oficial` preenchida com o link do anúncio oficial do estúdio ou da emissora, a mudança vai direto para a capa do site como aviso. Se não tiver, a mudança fica em `data/pendentes.json` para você revisar, e nada é publicado. Esse é o cuidado de sempre: uma única fonte pode estar errada, e o site não deve noticiar atraso com base só nela. Para publicar, confira o anúncio oficial, cole o link em `fonte_oficial` e, na próxima atualização, o aviso sai. Você também pode mover o item de `pendentes.json` para `avisos.json` manualmente, se preferir.

## Custos

Para este projeto, o custo mínimo é zero. O GitHub Actions e o GitHub Pages são gratuitos em repositórios públicos, sem limite de minutos para o workflow, e a API do AniList não exige chave para leitura. Se você mantiver o repositório privado, o plano gratuito inclui 2.000 minutos de Actions por mês, o que sobra para duas execuções semanais. O domínio próprio (opcional) costuma custar algo entre R$ 40 e R$ 100 por ano, e varia conforme a extensão e o registrador. Se mais tarde você usar IA paga para escrever textos automaticamente, cada geração é cobrada por uso. Confira os preços atuais nas páginas oficiais antes de decidir, porque mudam com frequência.

## O que é automático e o que é seu

Automático: consultar os dados, atualizar fichas, próximo episódio, status e nota da comunidade; criar páginas para animes novos que você adicionar; registrar mudanças de data; atualizar a capa e o site.

Seu: escolher os animes, escrever as análises e as notas, verificar fontes oficiais antes de publicar avisos, e decidir quando adicionar uma imagem (com licença clara). Este projeto não inclui imagens de capa de propósito, para evitar problemas de direitos autorais. Você pode adicionar depois, com imagens que o estúdio ou a plataforma liberem para divulgação.

## Limitações conhecidas

Eu escrevi o código, mas não consegui executá-lo contra a API real daqui, porque o domínio do AniList não está liberado no meu ambiente. Por isso, a primeira execução é o teste de verdade. Se algo falhar, a mensagem de erro aparece na aba Actions, e você pode me mandar o texto para eu corrigir. O script também está preparado para não apagar dados bons quando a API falha: se uma consulta der erro, o registro anterior é mantido.

## Próximos passos possíveis

Página de temporada com todos os animes listados, filtro por dia da semana, um índice de todas as análises com notas, e, mais tarde, a aba de filmes e séries.
