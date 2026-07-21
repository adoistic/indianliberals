export default {
  fetch(request) {
    const url = new URL(request.url);
    url.hostname = "indianliberals.in";
    return Response.redirect(url.toString(), 301);
  },
};
