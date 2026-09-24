"""Pruebas unitarias del simulador OSI.  Ejecutar:  python -m unittest -v"""

import unittest

import osi_core as osi


class PruebasBase64(unittest.TestCase):
    def test_ida_y_vuelta(self):
        for texto in ["Hola", "ñandú ¿?¡!", "emoji 🚀", "[L7|x=y]"]:
            self.assertEqual(osi.decodificar_base64(osi.codificar_base64(texto)), texto)

    def test_solo_caracteres_base64(self):
        self.assertRegex(osi.codificar_base64("Redes [OSI] ; = |"), r"^[A-Za-z0-9+/=]+$")


class PruebasBits(unittest.TestCase):
    def test_bits_ida_y_vuelta(self):
        self.assertEqual(osi.bits_a_texto(osi.texto_a_bits("Trama ñ")), "Trama ñ")

    def test_ocho_bits_por_byte(self):
        self.assertEqual(osi.texto_a_bits("A"), "01000001")

    def test_bits_invalidos(self):
        with self.assertRaises(osi.ErrorOSI):
            osi.bits_a_texto("0101")


class PruebasEncapsulamiento(unittest.TestCase):
    def setUp(self):
        self.pasos, self.bits = osi.encapsular("Hola", osi.PC_A, osi.PC_B, "S-1234")

    def test_siete_capas_en_orden(self):
        self.assertEqual([p.capa for p in self.pasos], [7, 6, 5, 4, 3, 2, 1])

    def test_pdu_por_capa(self):
        self.assertEqual([p.pdu for p in self.pasos],
                         ["Datos", "Datos", "Datos", "Segmento", "Paquete", "Trama", "Bits"])

    def test_la_pdu_crece_hasta_enlace(self):
        tamanos = [len(p.contenido) for p in self.pasos[:6]]
        self.assertEqual(tamanos, sorted(tamanos))

    def test_trama_tiene_encabezado_y_trailer(self):
        trama = self.pasos[5].contenido
        self.assertTrue(trama.startswith("[L2|"))
        self.assertIn("[FCS|crc32=", trama)

    def test_salida_final_son_bits(self):
        self.assertTrue(set(self.bits) <= {"0", "1"})


class PruebasTransmision(unittest.TestCase):
    def test_mensajes_recuperados(self):
        for msg in ["Hola PC-B", "Acentos: áéíóú ñ", "Símbolos [ ] ; = |", "🚀 emoji", "x" * 500]:
            r = osi.transmitir(msg)
            self.assertTrue(r.exito, r.error)
            self.assertEqual(r.mensaje_recibido, msg)
            self.assertEqual([p.capa for p in r.pasos_desencapsulamiento], [1, 2, 3, 4, 5, 6, 7])

    def test_mensaje_vacio(self):
        with self.assertRaises(ValueError):
            osi.transmitir("   ")

    def test_ruido_detectado_en_enlace(self):
        for _ in range(20):
            r = osi.transmitir("Mensaje con ruido", ruido=True)
            self.assertFalse(r.exito)
            self.assertEqual(r.capa_error, 2)

    def test_mac_equivocada(self):
        intruso = osi.Dispositivo("PC-C", "192.168.1.30", "CC:CC:CC:00:00:0C", 8080)
        _, bits = osi.encapsular("Hola", osi.PC_A, osi.PC_B, "S-1")
        with self.assertRaises(osi.ErrorOSI) as ctx:
            osi.desencapsular(bits, intruso, "S-1")
        self.assertEqual(ctx.exception.capa, 2)

    def test_sesion_equivocada(self):
        _, bits = osi.encapsular("Hola", osi.PC_A, osi.PC_B, "S-1")
        with self.assertRaises(osi.ErrorOSI) as ctx:
            osi.desencapsular(bits, osi.PC_B, "S-2")
        self.assertEqual(ctx.exception.capa, 5)


if __name__ == "__main__":
    unittest.main()
