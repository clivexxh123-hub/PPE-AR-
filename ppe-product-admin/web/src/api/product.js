import request from "./request";

export function getCategories() {
  return request({
    url: "/categories",
    method: "get"
  });
}

export function getProducts(params) {
  return request({
    url: "/products",
    method: "get",
    params
  });
}

export function getProductDetail(id) {
  return request({
    url: `/products/${id}`,
    method: "get"
  });
}

export function updateProduct(id, data) {
  return request({
    url: `/products/${id}`,
    method: "put",
    data
  });
}

export function uploadProductFile(id, data) {
  return request({
    url: `/products/${id}/files`,
    method: "post",
    data,
    headers: {
      "Content-Type": "multipart/form-data"
    }
  });
}

export function deleteProductFile(id) {
  return request({
    url: `/files/${id}`,
    method: "delete"
  });
}
