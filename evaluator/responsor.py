import torch
import torch.nn as nn

from helper import PAD ,SOS, EOS, UNK
from util.word_segment import ws

class Responsor(object):

    def __init__(self, dataset, encoder, decoder, max_seq_len, replace_unk=True, USE_CUDA=True):

        self.dataset = dataset

        self.encoder = encoder
        self.decoder = decoder

        self.max_seq_len = max_seq_len
        self.replace_unk = replace_unk
        self.USE_CUDA = USE_CUDA

    def response(self, src_text):
        src_sent = ws(src_text)
        # with torch.no_grad():
        response_seqs = self.forward(src_sent)
        return "".join(self.ids2tokens(response_seqs))

    def forward(self, src_sent):
        """
            e.g.
                Assumed w2id = {"<PAD>": 0, "<SOS>":1, "<EOS>": 2, "<UNK>": 3, "what": 4, "do": 5, "you": 6, "have": 7, "I": 8, "an": 9, "apple": 10}

                src_sent: ["what", "do", "you", "have"]
                src_seqs: [4, 5, 6, 7, 2]
                src_lens: len(src_sent) + 1

                out_sent: ["I", "have", "an", "apple"]
                out_seqs: [8, 7, 9, 10, 2]

        """

        src_seqs = torch.LongTensor([self.dataset.tokens2ids(tokens=src_sent,
                                                            token2id=self.dataset.vocab.token2id,
                                                            append_SOS=False, append_EOS=True)]).transpose(0,1) # shape: (seq_len, 1)

        src_lens = torch.LongTensor([src_seqs.size(0)]) # shape: (seq_len + 1,)


        # Decoder's input
        input_seq = torch.LongTensor([SOS])


        # Store output words and attention states
        out_seqs = []
        all_attention_weights = torch.zeros(self.max_seq_len, src_seqs.size(0))

        # Move variables from CPU to GPU.
        if self.USE_CUDA:
            src_seqs = src_seqs.cuda()
            src_lens = src_lens.cuda()
            input_seq = input_seq.cuda()

        # -------------------------------------
        # Evaluation mode (disable dropout)
        # -------------------------------------
        self.encoder.eval()
        self.decoder.eval()

        # -------------------------------------
        # Forward encoder
        # -------------------------------------
        # encoder_outputs: (max_seq_len, batch_size=1, hidden_size)
        # encoder_hidden:  (num_layers, batch_size=1, num_directions * hidden_size)
        # -------------------------------------
        encoder_outputs, encoder_hidden = self.encoder(src_seqs)

        # -------------------------------------
        # Forward decoder
        # -------------------------------------
        # Initialize decoder's hidden state as encoder's last hidden state.
        decoder_hidden = encoder_hidden

        # Run through decoder one time step at a time.
        for t in range(self.max_seq_len):

            # decoder returns:
            # - decoder_output   : (batch_size, vocab_size)
            # - decoder_hidden   : (num_layers, batch_size, hidden_size)
            # - attention_weights: (batch_size, max_src_len)
            decoder_output, decoder_hidden, attention_weights \
            = self.decoder(input_seq, decoder_hidden, encoder_outputs, src_lens)

            # Store attention weights.
            # .squeeze(0): remove `batch_size` dimension since batch_size=1
            all_attention_weights[t] = attention_weights.squeeze(0).cpu()


            # Choose top word from decoder's output
            prob, token_id = decoder_output.data.topk(1)    # (batch_size=1, 1), (batch_size=1, 1)
            token_id = token_id[0].item()                   # get value

            if token_id == EOS:
                break
            elif token_id == UNK and self.replace_unk:
                # Replace unk by selecting the source token with the highest attention score.
                score, idx = all_attention_weights[t].max(0)
                token_id = src_seqs[idx]

            out_seqs.append(token_id)


            # Next input is chosen word
            input_seq = torch.LongTensor([token_id])
            if self.USE_CUDA:
                input_seq = input_seq.cuda()

        return out_seqs

    def ids2tokens(self, seqs):
        return [self.dataset.vocab.id2token[id] for id in seqs]


from models.encoder import encoder
from models.decoder import decoder
from dataset.gen_dataset import gen_dataset
from opts import opts, USE_CUDA

responsor = Responsor(dataset=gen_dataset,
                        encoder=encoder,
                        decoder=decoder,
                        max_seq_len=opts.max_seq_len,
                        replace_unk=True,
                        USE_CUDA=USE_CUDA)
