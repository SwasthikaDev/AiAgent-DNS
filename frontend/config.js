// Service URLs. Defaults match the docker-compose port mapping.
// Override at runtime via query params, e.g.
//   /ui/?index=http://localhost:18000&facts1=http://localhost:18001
// Useful if you ran the stack on alternate ports because :8000 was busy.

(function () {
  const qs = new URLSearchParams(window.location.search);
  const get = (k, d) => qs.get(k) || d;
  window.NANDA_CONFIG = {
    INDEX_URL: get("index", "http://localhost:8000"),
    FACTS_PRIMARY_URL: get("facts1", "http://localhost:8001"),
    FACTS_PRIVATE_URL: get("facts2", "http://localhost:8002"),
    AGENT_ECHO_URL: get("agent1", "http://localhost:8010"),
    AGENT_TRANSLATE_URL: get("agent2", "http://localhost:8011"),
    ADAPTIVE_RESOLVER_URL: get("resolver", "http://localhost:8020"),
  };
})();
