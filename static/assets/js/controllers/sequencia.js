angular.module('deciframeApp').controller('SequenciaController', function($http, $window, ngProgressFactory, $anchorScroll, $location, GENEROS) {
  var vm = this;
  vm.sequenciasFamosas = [];
  vm.minhaSequencia = { acordes: [] };
  vm.novaSequencia = "";
  vm.erroCadastro = "";
  vm.erroCatalogo = "";
  vm.isCriando = false;
  vm.isSearching = false;
  vm.showSearchResultsCount = false;
  vm.esfigeSpeech = "";
  vm.musics = [];
  vm.generos = GENEROS;
  vm.meuGenero = "";
  vm.progressbar = ngProgressFactory.createInstance();

  var montarSequencia = function(sequencia) {
    return {
      id: sequencia.id,
      origem: sequencia.origem,
      acordes: sequencia.acordes.map(function(acorde) {
        return { acorde: acorde, cor: '#2E1C74' };
      })
    };
  };

  vm.carregarSequencias = function(aoCarregar) {
    $http.get('sequencias')
      .success(function(data) {
        vm.sequenciasFamosas = data.map(montarSequencia);
        vm.erroCatalogo = "";
        if (aoCarregar) {
          aoCarregar();
        }
      })
      .error(function() {
        vm.erroCatalogo = "Não foi possível carregar o catálogo de sequências.";
      });
  };

  vm.temAcorde = function(acorde) {
    if (vm.minhaSequencia.acordes) {
      return (vm.minhaSequencia.acordes.indexOf(acorde) > -1);
    } else {
      return false;
    }
  };

  vm.pesquisarPorSequencia = function(sequencia) {
    if (sequencia) {
      vm.minhaSequencia = sequencia;
    }
    if (!vm.minhaSequencia || vm.minhaSequencia.id === undefined) {
      return;
    }

    vm.progressbar.start();
    vm.esfigeSpeech = "Procurando músicas com base na sequencia...";
    vm.isSearching = true;
    vm.musics = [];

    var searchString = "similares?sequencia_id=".concat(encodeURIComponent(vm.minhaSequencia.id));
    if (vm.meuGenero !== "" && vm.meuGenero !== null) {
      searchString += "&generos=".concat(encodeURIComponent(vm.meuGenero));
    }

    $http.get(searchString)
      .success(function(data) {
        vm.progressbar.complete();
        vm.esfigeSpeech = "Encontrei essas músicas";
        vm.isSearching = false;
        vm.showSearchResultsCount = true;
        vm.musics = data;
      })
      .error(function() {
        vm.progressbar.complete();
        vm.esfigeSpeech = "Ops! Algo errado.";
        vm.isSearching = false;
        vm.showSearchResultsCount = false;
      });
  };

  vm.cadastrarSequencia = function() {
    var acordes = vm.novaSequencia.split(',')
      .map(function(acorde) { return acorde.trim(); })
      .filter(function(acorde) { return acorde.length > 0; });

    vm.erroCadastro = "";
    if (acordes.length === 0) {
      vm.erroCadastro = "Digite ao menos um acorde separado por vírgula.";
      return;
    }

    vm.isCriando = true;
    $http.post('sequencias', { acordes: acordes })
      .success(function(data) {
        vm.isCriando = false;
        vm.novaSequencia = "";
        vm.carregarSequencias(function() {
          var criada = vm.sequenciasFamosas.filter(function(sequencia) {
            return sequencia.id === data.id;
          })[0];
          if (criada) {
            vm.pesquisarPorSequencia(criada);
          }
        });
      })
      .error(function(data) {
        vm.isCriando = false;
        if (data && data.erro === 'sequencia_duplicada') {
          vm.erroCadastro = "Essa sequência já está cadastrada.";
        } else if (data && data.mensagem) {
          vm.erroCadastro = data.mensagem;
        } else {
          vm.erroCadastro = "Não foi possível cadastrar a sequência.";
        }
      });
  };

  vm.limparPesquisa = function() {
    vm.minhaSequencia = { acordes: [] };
    vm.musics = [];
  };

  vm.goToLirics = function(music) {
    $window.open(music.url);
  };

  vm.goToResults = function() {
    vm.showSearchResultsCount = false;
    $("body").animate({scrollTop: $("#results").offset().top}, "slow");
  };

  vm.carregarSequencias();
});
