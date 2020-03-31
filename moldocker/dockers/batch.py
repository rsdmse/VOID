import numpy as np
from pymatgen.core import Structure

from .base import Docker
from moldocker import utils
from moldocker.geometry.rotation import random_rotation_matrices


class BatchDocker(Docker):
    def rotate_guest(self, attempts):
        # (N, num_atoms, 3) matrix
        coords = np.repeat(self.guest.cart_coords[None, ...], attempts, axis=0)

        # (N, 3, 3) matrix
        rotation = random_rotation_matrices(attempts)

        # (N, num_atoms, 3) matrix
        return np.matmul(coords, rotation.swapaxes(-1, -2))

    def translate_host(self, point, attempts):
        """Translates all nodes of the host to the given coords.

        Args:
            coords (np.array): (3, ) array with cartesian coordinates.
        """

        translated = self.host.cart_coords - point

        return np.repeat(translated[None, ...], attempts, axis=0)

    def dock_to_point(self, point, attempts):
        host_batch = self.translate_host(point, attempts)
        guest_batch = self.rotate_guest(attempts)

        dist_matrices = self.get_distance_matrices(host_batch, guest_batch)

        poses = [
            self._pose_from_coords(hcoords, gcoords)
            for hcoords, gcoords, dm in zip(host_batch, guest_batch, dist_matrices)
            if self.satisfy_distance_criteria(dm)
        ]

        return poses

    def _pose_from_coords(self, host_coords, guest_coords):
        coords = np.concatenate([host_coords, guest_coords], axis=0)

        labels = ["host"] * len(self.host) + ["guest"] * len(self.guest)

        # TODO: add previous properties if they already exist in
        # the host
        props = {"label": labels}

        return Structure(
            species=(self.host.species + self.guest.species),
            coords=coords,
            lattice=self.host.lattice.matrix,
            coords_are_cartesian=True,
            site_properties=props,
        )

    def get_distance_matrices(self, host_batch, guest_batch):
        frac_host = self.host.lattice.get_fractional_coords(
            host_batch.reshape(-1, 3)
        ).reshape(host_batch.shape)
        frac_guest = self.host.lattice.get_fractional_coords(
            guest_batch.reshape(-1, 3)
        ).reshape(guest_batch.shape)

        distance_matrices = [
            self.host.lattice.get_all_distances(f1, f2)
            for f1, f2 in zip(frac_host, frac_guest)
        ]

        return distance_matrices

    def satisfy_distance_criteria(self, dmatrix):
        return dmatrix.min() > 1.5
